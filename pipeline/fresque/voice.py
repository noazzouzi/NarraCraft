"""Synthèse de la voix, et l'alignement qui en découle.

Un fichier audio par beat, puis une piste unique concaténée. Synthétiser
beat par beat achète deux choses : un beat se refait seul, et — surtout —
la durée **réelle** de chaque beat est mesurée au lieu d'être devinée.

Ces durées réelles deviennent les points de coupe du montage, donc chaque
coupe tombe exactement là où la narration passe à autre chose. La position
d'un mot *à l'intérieur* d'un beat reste répartie au poids syllabique :
aucun des moteurs n'expose de timing par mot, et sur une trentaine de mots
la répartition pondérée suffit aux sous-titres. `alignment.json` dit lequel
est lequel dans son champ `source`.

TROIS MOTEURS
=============
`voix.provider` choisit :

- `kokoro` — local, gratuit, sans réseau. 54 voix, dont une seule
  française, féminine.
- `edge` — les voix neuronales de Microsoft Edge, gratuites et sans clé,
  mais par le réseau. 322 voix, dont 13 francophones et 7 masculines.
- `elevenlabs` — payant, avec une clé dans `ELEVENLABS_API_KEY`. Ses voix
  multilingues parlent la langue du texte plutôt que la leur.

Les trois décrivent leur catalogue de façon incompatible — deux lettres de
préfixe chez Kokoro, du JSON Microsoft chez Edge, des étiquettes libres
chez ElevenLabs. `Voix` et `catalogue()` les normalisent, pour que la
bibliothèque se filtre par langue et par sexe sans trois interfaces.

Ce qu'ils ne font pas pareil, et qui compte : le silence qu'ils laissent
autour d'une phrase. Mesuré sur trois phrases courtes —

    moteur                          tête    queue
    kokoro ff_siwis                0,042 s  0,149 s
    fr-FR-RemyMultilingualNeural   0,174 s  0,587 s
    fr-FR-HenriNeural              0,213 s  0,918 s

Edge emballe donc chaque phrase dans plus d'une seconde de vide. Le moteur
Edge rogne donc son propre silence de tête et de queue.

QUI POSE LES PAUSES
===================
Ce qui suit vient d'une mesure, après qu'un film entier a sonné mécanique.

Les moteurs en ligne savent lire un paragraphe : sur un beat entier, Edge
laisse 0,35 s après une virgule et 1,30 s après un point. La hiérarchie
existe — elle est seulement trop large pour un documentaire. Kokoro, lui,
laisse 0,10 s dans les deux cas : chez lui la hiérarchie n'existe pas.

`_say_beat` traite donc les deux cas différemment, et `marque_les_phrases`
dit lequel s'applique. Resserrer les pauses d'un moteur qui les marque coûte
un appel au lieu de huit, et garde sa prosodie d'un bout à l'autre du beat.
Découper le beat pour les trois, ce que faisait ce module, produisait des
pauses toutes identiques au millième près — le défaut audible de
`la-faillite-de-subway`, mesuré dans le docstring de `_say_beat`.

`narration.pause_phrase_s` reste la cible dans les deux chemins.
"""
from __future__ import annotations

import re
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import config
from .align import syllables, _tokenize  # noqa: PLC2701 — same module family
from .script_parser import Beat, Script

SAMPLE_RATE = 24_000


class VoiceError(RuntimeError):
    pass


def _paths() -> tuple[Path, Path]:
    root = config.repo_root()
    model = root / str(config.get("voix", "kokoro", "model", default="models/kokoro-v1.0.onnx"))
    voices = root / str(config.get("voix", "kokoro", "voices", default="models/voices-v1.0.bin"))
    missing = [p for p in (model, voices) if not p.is_file()]
    if missing:
        raise VoiceError(
            "Modèle Kokoro absent :\n  "
            + "\n  ".join(str(p) for p in missing)
            + "\n\nLes télécharger depuis les releases de kokoro-onnx :\n"
            "  https://github.com/thewh1teagle/kokoro-onnx/releases"
        )
    return model, voices


def _engine():
    try:
        from kokoro_onnx import Kokoro
    except ImportError as error:  # pragma: no cover - environment dependent
        raise VoiceError(
            "kokoro-onnx n'est pas installé : pip install kokoro-onnx soundfile"
        ) from error
    model, voices = _paths()
    return Kokoro(str(model), str(voices))


# --- Le catalogue ------------------------------------------------------------

@dataclass(frozen=True)
class Voix:
    """Une voix, décrite de la même façon chez les trois fournisseurs.

    Les trois catalogues n'ont rien en commun : Kokoro encode la langue et
    le sexe dans deux lettres de préfixe, Edge rend du JSON Microsoft,
    ElevenLabs des étiquettes libres. Les normaliser ici est le seul moyen
    d'avoir une bibliothèque filtrable sans écrire trois interfaces.
    """
    id: str
    nom: str
    langue: str          # locale, « fr-FR » — vide si le moteur l'ignore
    genre: str           # « homme », « femme » ou « inconnu »
    detail: str = ""

    @property
    def code_langue(self) -> str:
        """« fr » pour « fr-FR » — ce sur quoi le filtre porte."""
        return self.langue.split("-")[0].lower()


def _genre(brut: str) -> str:
    valeur = (brut or "").strip().lower()
    if valeur in ("male", "m", "homme"):
        return "homme"
    if valeur in ("female", "f", "femme"):
        return "femme"
    return "inconnu"


def catalogue(provider: str | None = None) -> list[Voix]:
    """Les voix d'un fournisseur. Trié par langue puis par nom."""
    nom = provider or str(config.get("voix", "provider", default="kokoro"))
    classe = MOTEURS.get(nom)
    if classe is None:
        raise VoiceError(
            f"`{nom}` n'est pas un fournisseur de voix. "
            f"Choisir parmi : {', '.join(sorted(MOTEURS))}."
        )
    voix = classe.catalogue()
    return sorted(voix, key=lambda v: (v.code_langue, v.genre, v.nom))


def filtrer(voix: list[Voix], langue: str = "", genre: str = "") -> list[Voix]:
    """Les deux filtres de la bibliothèque : langue et sexe."""
    code = langue.split("-")[0].lower() if langue else ""
    attendu = _genre(genre) if genre else ""
    return [
        v for v in voix
        if (not code or v.code_langue == code)
        and (not attendu or v.genre == attendu)
    ]


# --- Les moteurs -------------------------------------------------------------

class Moteur:
    """Ce qu'un moteur de voix doit savoir faire : dire une phrase.

    `pause_naturelle_s` est le silence que le moteur laisse déjà après un
    point. Le pipeline l'ôte de celui qu'il ajoute, sinon les deux
    s'additionnent et la pause réelle dépasse celle qui est demandée.

    `marque_les_phrases` dit si le moteur fait lui-même la différence entre
    une virgule et un point quand on lui donne un beat entier. Voir
    `_say_beat` : de cette réponse dépend le fait qu'on lui livre le beat
    d'un bloc ou phrase par phrase, et c'est le réglage qui décide si la
    narration sonne humaine ou mécanique.
    """

    nom: str = ""
    pause_naturelle_s: float = 0.0
    marque_les_phrases: bool = False

    @classmethod
    def catalogue(cls) -> list["Voix"]:  # pragma: no cover - interface
        """Les voix disponibles. Sans instancier le moteur : lister ne doit
        pas charger trois cents mégaoctets de modèle ni ouvrir de session."""
        raise NotImplementedError

    def dire(self, phrase: str):  # pragma: no cover - interface
        raise NotImplementedError

    def fiche(self) -> dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError


class MoteurKokoro(Moteur):
    nom = "kokoro"
    #: Mesuré sur ff_siwis : 0,10 s à vitesse 0,75, 0,12 s à 0,82 — à peine
    #: plus qu'après une virgule.
    pause_naturelle_s = 0.10

    #: Kokoro encode langue et sexe dans les deux premières lettres du nom
    #: d'une voix : `ff_siwis` est française et féminine. C'est la seule
    #: description qu'il en donne — il n'y a pas de catalogue ailleurs.
    LANGUES = {
        "a": "en-US", "b": "en-GB", "e": "es-ES", "f": "fr-FR", "h": "hi-IN",
        "i": "it-IT", "j": "ja-JP", "p": "pt-BR", "z": "zh-CN",
    }

    @classmethod
    def catalogue(cls) -> list[Voix]:
        import numpy as np

        _, voices = _paths()
        # Le fichier de voix est un npz : ses clés sont les noms. Les lire
        # coûte onze millisecondes, contre plusieurs secondes pour charger
        # le modèle ONNX de trois cent vingt-cinq mégaoctets.
        with np.load(voices) as archive:
            noms = sorted(archive.files)

        sorties = []
        for identifiant in noms:
            prefixe = identifiant[:2] if "_" in identifiant else ""
            langue = cls.LANGUES.get(prefixe[:1], "")
            genre = _genre({"f": "femme", "m": "homme"}.get(prefixe[1:2], ""))
            joli = identifiant.split("_", 1)[-1].capitalize()
            sorties.append(Voix(
                id=identifiant, nom=joli, langue=langue, genre=genre,
                detail="locale, sans réseau",
            ))
        return sorties

    def __init__(self, voix: str = "") -> None:
        self.kokoro = _engine()
        self.voice = voix or str(
            config.get("voix", "kokoro", "voice", default="ff_siwis"))
        self.lang = str(config.get("voix", "kokoro", "lang", default="fr-fr"))
        self.speed = float(config.get("voix", "kokoro", "speed", default=0.82))

    def dire(self, phrase: str):
        return self.kokoro.create(
            phrase, voice=self.voice, speed=self.speed, lang=self.lang
        )

    def fiche(self) -> dict[str, Any]:
        return {
            "provider": "kokoro",
            "voice": self.voice,
            "lang": self.lang,
            "speed": self.speed,
        }


#: Sous ce niveau, on considère que le moteur ne dit rien. Relevé sur les
#: deux voix Edge : leur silence est un vrai zéro numérique, pas un souffle.
_SEUIL_SILENCE = 0.01

#: Ce qu'on laisse de part et d'autre après avoir rogné. Sans marge, une
#: occlusive initiale — un « p », un « t » — se fait couper net.
_MARGE_ROGNAGE_S = 0.03


def _rogner(samples, rate: int):
    """Ôte le silence de tête et de queue, en gardant une marge."""
    import numpy as np

    x = np.asarray(samples, dtype="float32")
    fort = np.abs(x) > _SEUIL_SILENCE
    if not fort.any():
        return x
    marge = int(_MARGE_ROGNAGE_S * rate)
    debut = max(int(np.argmax(fort)) - marge, 0)
    fin = min(len(x) - int(np.argmax(fort[::-1])) + marge, len(x))
    return x[debut:fin]


class MoteurEdge(Moteur):
    """Les voix neuronales de Microsoft Edge. Gratuites, sans clé, en ligne.

    Le silence est rogné à la sortie : voir la mesure en tête de module.
    Après rognage il ne reste rien à compenser, donc la pause que pose le
    pipeline est celle qu'il demande.
    """

    nom = "edge"
    pause_naturelle_s = 0.0
    #: Mesuré : sur un beat entier, Edge laisse 0,35 s après une virgule et
    #: 1,30 s après un point. La hiérarchie existe, elle est juste trop
    #: large — on la resserre, on ne la refait pas.
    marque_les_phrases = True

    @classmethod
    def catalogue(cls) -> list[Voix]:
        import asyncio

        try:
            import edge_tts
        except ImportError as error:  # pragma: no cover - environment dependent
            raise VoiceError(
                "edge-tts n'est pas installé : pip install edge-tts soundfile"
            ) from error
        try:
            toutes = asyncio.run(edge_tts.list_voices())
        except Exception as error:  # noqa: BLE001 - réseau, forme variable
            raise VoiceError(
                f"catalogue Edge indisponible — {str(error)[:120]}"
            ) from error

        return [
            Voix(
                id=v["ShortName"],
                nom=v["ShortName"].split("-")[-1].removesuffix("Neural"),
                langue=v.get("Locale", ""),
                genre=_genre(v.get("Gender", "")),
                detail=", ".join(
                    (v.get("VoiceTag") or {}).get("VoicePersonalities") or []
                ),
            )
            for v in toutes
        ]

    def __init__(self, voix: str = "") -> None:
        self.voice = voix or str(
            config.get("voix", "edge", "voice", default="fr-FR-HenriNeural"))
        self.rate = str(config.get("voix", "edge", "rate", default="+0%"))
        self.volume = str(config.get("voix", "edge", "volume", default="+0%"))
        self.pitch = str(config.get("voix", "edge", "pitch", default="+0Hz"))
        try:
            import edge_tts  # noqa: F401
            import soundfile  # noqa: F401
        except ImportError as error:  # pragma: no cover - environment dependent
            raise VoiceError(
                "edge-tts n'est pas installé : pip install edge-tts soundfile"
            ) from error

    def dire(self, phrase: str):
        import asyncio
        import io
        import os

        import edge_tts
        import soundfile as sf

        async def chercher() -> bytes:
            # `proxy` sert les réseaux d'entreprise ; sans variable
            # d'environnement il vaut None et ne change rien.
            parole = edge_tts.Communicate(
                phrase, self.voice, rate=self.rate,
                volume=self.volume, pitch=self.pitch,
                proxy=os.environ.get("HTTPS_PROXY"),
            )
            tampon = io.BytesIO()
            async for morceau in parole.stream():
                if morceau["type"] == "audio":
                    tampon.write(morceau["data"])
            return tampon.getvalue()

        brut = asyncio.run(chercher())
        if not brut:
            raise VoiceError(
                f"Edge n'a rien rendu pour « {phrase[:40]}… » — "
                f"vérifier la voix `{self.voice}` et la connexion."
            )
        samples, rate = sf.read(io.BytesIO(brut), dtype="float32", always_2d=False)
        return _rogner(samples, rate), rate

    def fiche(self) -> dict[str, Any]:
        return {
            "provider": "edge",
            "voice": self.voice,
            "rate": self.rate,
            "volume": self.volume,
            "pitch": self.pitch,
        }


class MoteurElevenLabs(Moteur):
    """Les voix d'ElevenLabs. Payantes, par le réseau, avec une clé.

    La clé vit dans `ELEVENLABS_API_KEY`, jamais dans le dépôt et jamais
    dans une commande. Sans elle, le moteur le dit et s'arrête — il ne
    tente pas un appel qui reviendrait en 401.

    Le silence est rogné comme chez Edge : tout moteur en ligne emballe ses
    phrases, et le rythme d'un documentaire se pose ici, pas chez le
    fournisseur.
    """

    nom = "elevenlabs"
    pause_naturelle_s = 0.0
    #: Comme Edge : un modèle multilingue lit la ponctuation d'un paragraphe.
    marque_les_phrases = True

    API = "https://api.elevenlabs.io/v1"

    @staticmethod
    def cle() -> str:
        import os

        cle = os.environ.get("ELEVENLABS_API_KEY", "").strip()
        if not cle:
            raise VoiceError(
                "ELEVENLABS_API_KEY n'est pas définie. La poser dans "
                "l'environnement — jamais dans le dépôt, jamais dans une "
                "ligne de commande."
            )
        return cle

    @classmethod
    def catalogue(cls) -> list[Voix]:
        import requests

        reponse = requests.get(
            f"{cls.API}/voices", headers={"xi-api-key": cls.cle()}, timeout=30,
        )
        if reponse.status_code == 401:
            raise VoiceError("ELEVENLABS_API_KEY refusée par ElevenLabs.")
        reponse.raise_for_status()

        sorties = []
        for brut in reponse.json().get("voices", []):
            etiquettes = brut.get("labels") or {}
            sorties.append(Voix(
                id=brut.get("voice_id", ""),
                nom=brut.get("name", ""),
                # ElevenLabs ne rend pas de locale : ses voix multilingues
                # parlent la langue du texte. On déclare celle du projet.
                langue=str(etiquettes.get("language", "")
                           or config.get("production", "langue", default="fr")),
                genre=_genre(etiquettes.get("gender", "")),
                detail=", ".join(
                    str(etiquettes[c]) for c in ("accent", "age", "use_case")
                    if etiquettes.get(c)
                ),
            ))
        return sorties

    def __init__(self, voix: str = "") -> None:
        self.voice = voix or str(
            config.get("voix", "elevenlabs", "voice", default=""))
        self.model = str(config.get(
            "voix", "elevenlabs", "model", default="eleven_multilingual_v2"))
        self.stabilite = float(config.get(
            "voix", "elevenlabs", "stabilite", default=0.5))
        self.similarite = float(config.get(
            "voix", "elevenlabs", "similarite", default=0.75))
        if not self.voice:
            raise VoiceError(
                "`voix.elevenlabs.voice` est vide — choisir une voix dans la "
                "bibliothèque avant de synthétiser."
            )
        self._cle = self.cle()
        try:
            import soundfile  # noqa: F401
        except ImportError as error:  # pragma: no cover - environment dependent
            raise VoiceError("soundfile n'est pas installé") from error

    def dire(self, phrase: str):
        import io

        import requests
        import soundfile as sf

        reponse = requests.post(
            f"{self.API}/text-to-speech/{self.voice}",
            headers={"xi-api-key": self._cle, "accept": "audio/mpeg"},
            json={
                "text": phrase,
                "model_id": self.model,
                "voice_settings": {
                    "stability": self.stabilite,
                    "similarity_boost": self.similarite,
                },
            },
            timeout=120,
        )
        if reponse.status_code == 401:
            raise VoiceError("ELEVENLABS_API_KEY refusée par ElevenLabs.")
        if reponse.status_code == 429:
            raise VoiceError(
                "quota ElevenLabs atteint — la synthèse s'arrête ici plutôt "
                "que de réessayer pendant une heure."
            )
        reponse.raise_for_status()
        if not reponse.content:
            raise VoiceError(f"ElevenLabs n'a rien rendu pour « {phrase[:40]}… »")

        samples, rate = sf.read(
            io.BytesIO(reponse.content), dtype="float32", always_2d=False)
        return _rogner(samples, rate), rate

    def fiche(self) -> dict[str, Any]:
        return {
            "provider": "elevenlabs",
            "voice": self.voice,
            "model": self.model,
            "stabilite": self.stabilite,
            "similarite": self.similarite,
        }


MOTEURS: dict[str, type[Moteur]] = {
    "kokoro": MoteurKokoro,
    "edge": MoteurEdge,
    "elevenlabs": MoteurElevenLabs,
}


def moteur(provider: str | None = None, voix: str = "") -> Moteur:
    """Le moteur que `voix.provider` désigne, ou celui qu'on lui impose.

    Les deux arguments servent à écouter une voix avant de la choisir :
    l'audition ne doit rien écrire dans `projet.yaml`, sinon écouter et
    décider seraient le même geste.
    """
    nom = provider or str(config.get("voix", "provider", default="kokoro"))
    classe = MOTEURS.get(nom)
    if classe is None:
        raise VoiceError(
            f"`voix.provider: {nom}` n'existe pas. "
            f"Choisir parmi : {', '.join(sorted(MOTEURS))}."
        )
    return classe(voix)


def _write_wav(path: Path, samples, rate: int) -> None:
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(np.asarray(samples, dtype="float32"), -1.0, 1.0)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        fh.writeframes((pcm * 32767).astype("<i2").tobytes())


def _time_words(beat: Beat, start: float, duration: float) -> list[dict[str, Any]]:
    """Spread a beat's words across its measured duration.

    Punctuation pauses are taken out first, then the remaining time is split
    between words in proportion to their syllable count.
    """
    words = _tokenize(beat.text)
    pauses = [pause for _, _, pause in words]
    pause_total = sum(pauses[:-1]) if len(pauses) > 1 else 0.0
    speech = max(duration - pause_total, duration * 0.35)
    # If punctuation would eat the whole beat, scale the pauses down instead.
    scale = (duration - speech) / pause_total if pause_total else 0.0

    weights = [syllables(word) for word, _, _ in words]
    total_weight = sum(weights) or 1

    clock = start
    timed: list[dict[str, Any]] = []
    for index, ((word, display, pause), weight) in enumerate(zip(words, weights)):
        span = speech * weight / total_weight
        timed.append({
            "t": word,
            "tx": display,
            "debut_s": round(clock, 3),
            "fin_s": round(clock + span, 3),
        })
        clock += span
        if index < len(words) - 1:
            clock += pause * scale
    return timed


#: Fin de phrase. Le point d'un « M. » ou d'un « 1. » n'en est pas une, d'où
#: l'exigence d'un espace et d'une majuscule — et le script, de toute façon,
#: ne doit plus contenir ni l'un ni l'autre (voir `lint.TTS_HAZARDS`).
_FIN_PHRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý])")

#: Au-delà de ce silence, on tient la pause pour une fin de phrase et non
#: pour une virgule. Relevé sur Edge : 0,35 s après une virgule, 1,30 s
#: après un point — la frontière est large, n'importe quelle valeur entre
#: les deux convient.
_SILENCE_DE_PHRASE_S = 0.55

#: Plancher : en dessous, une pause cesse de s'entendre comme une pause.
_PAUSE_MINIMALE_S = 0.12


def _caler_silences(samples, rate: int, cible: float):
    """Resserre les silences de fin de phrase sans les égaliser.

    Le moteur sait où sont les points — ses pauses le disent. Il les fait
    seulement trop longues pour un documentaire. On ramène donc la médiane
    des pauses longues sur `cible` et on applique le même facteur à toutes :
    celle qui était la plus longue le reste, la virgule n'est pas touchée.

    Écraser cette hiérarchie est exactement ce qui fait sonner une voix
    mécanique. Une pause de point et une pause de virgule qui durent le
    même temps, quatre cents fois de suite, s'entendent comme une machine.
    """
    import numpy as np

    x = np.asarray(samples, dtype="float32")
    longs = _silences(x, rate, _SILENCE_DE_PHRASE_S)
    if not longs:
        return x

    durees = [(fin - debut) / rate for debut, fin in longs]
    facteur = min(cible / float(np.median(durees)), 1.0)

    morceaux: list[Any] = []
    curseur = 0
    for (debut, fin), duree in zip(longs, durees):
        morceaux.append(x[curseur:debut])
        garde = max(duree * facteur, _PAUSE_MINIMALE_S)
        morceaux.append(np.zeros(int(garde * rate), dtype="float32"))
        curseur = fin
    morceaux.append(x[curseur:])
    return np.concatenate(morceaux)


def _silences(x, rate: int, mini: float) -> list[tuple[int, int]]:
    """Les plages muettes d'au moins `mini` secondes, en échantillons."""
    import numpy as np

    muet = np.abs(x) <= _SEUIL_SILENCE
    bord = np.diff(muet.astype(np.int8))
    debuts = np.flatnonzero(bord == 1) + 1
    fins = np.flatnonzero(bord == -1) + 1
    if len(muet) and muet[0]:
        debuts = np.r_[0, debuts]
    if len(muet) and muet[-1]:
        fins = np.r_[fins, len(x)]
    return [
        (int(a), int(b)) for a, b in zip(debuts, fins)
        if (b - a) / rate >= mini
    ]


def _say_beat(machine: Moteur, texte: str, phrase_gap: float):
    """Synthétise un beat, et pose le rythme que le montage attend.

    Le silence est la moitié du rythme : la voix de Frontier se tait un
    tiers du temps (`docs/analyse-frontier.md`). Restait à décider qui le
    place. Deux chemins, selon ce que le moteur sait faire.

    **Le moteur marque les phrases** (Edge, ElevenLabs). On lui donne le
    beat entier, d'un seul appel, et on se contente de resserrer les
    silences qu'il a posés (`_caler_silences`). Il garde alors sa prosodie
    d'un bout à l'autre du beat, et sa hiérarchie virgule / point.

    **Le moteur ne les marque pas** (Kokoro : un dixième de seconde après un
    point, à peine plus qu'après une virgule, et aucun réglage ne
    l'allonge). On découpe à la phrase et on insère le silence nous-mêmes.

    Ce choix n'est pas cosmétique. Le découpage systématique — ce que faisait
    ce module pour les trois moteurs — a produit la voix de `la-faillite-de-
    subway` : quarante-huit pauses de 0,450 s au millième près, dix-huit de
    0,400 s, et une pause de point qui durait exactement aussi longtemps
    qu'une pause de virgule. Mesuré sur le film : écart-type des pauses
    0,126 s contre 0,510 s pour le même texte dit d'un bloc. C'est
    précisément ce qu'on entend comme « robotique ».

    Et effet de bord utile, dans les deux cas : `align.estimate` modélisait
    déjà ces pauses comme du temps réel. Elles le sont.
    """
    import numpy as np

    if machine.marque_les_phrases:
        samples, rate = machine.dire(texte)
        return _caler_silences(samples, rate, phrase_gap), rate

    phrases = [p.strip() for p in _FIN_PHRASE.split(texte) if p.strip()]
    if len(phrases) <= 1:
        return machine.dire(texte)

    morceaux: list[Any] = []
    rate = SAMPLE_RATE
    for index, phrase in enumerate(phrases):
        samples, rate = machine.dire(phrase)
        morceaux.append(np.asarray(samples, dtype="float32"))
        manquant = phrase_gap - machine.pause_naturelle_s
        if index < len(phrases) - 1 and manquant > 0:
            morceaux.append(np.zeros(int(manquant * rate), dtype="float32"))
    return np.concatenate(morceaux), rate


def synthesize(
    script: Script,
    audio_dir: Path,
    progress: Callable[[int, int, float], None] | None = None,
) -> dict[str, Any]:
    """Render every beat, concatenate, and return the alignment."""
    import numpy as np

    machine = moteur()
    beat_gap = float(config.get("narration", "pause_entre_beats_s", default=0.4))
    act_gap = float(config.get("narration", "pause_entre_actes_s", default=1.2))
    phrase_gap = float(config.get("narration", "pause_phrase_s", default=0.45))

    beats_dir = audio_dir / "beats"
    beats_dir.mkdir(parents=True, exist_ok=True)

    pieces: list[Any] = []
    entries: list[dict[str, Any]] = []
    clock = 0.0
    previous_act: str | None = None

    for index, beat in enumerate(script.beats):
        if previous_act is not None:
            gap = act_gap if beat.act != previous_act else beat_gap
            pieces.append(np.zeros(int(gap * SAMPLE_RATE), dtype="float32"))
            clock += gap
        previous_act = beat.act

        samples, rate = _say_beat(machine, beat.text, phrase_gap)
        if rate != SAMPLE_RATE:
            raise VoiceError(f"Fréquence inattendue : {rate} Hz (attendu {SAMPLE_RATE}).")

        samples = np.asarray(samples, dtype="float32")
        duration = len(samples) / rate
        _write_wav(beats_dir / f"{beat.id}.wav", samples, rate)
        pieces.append(samples)

        entries.append({
            "id": beat.id,
            "acte": beat.act,
            "debut_s": round(clock, 3),
            "fin_s": round(clock + duration, 3),
            "duree_s": round(duration, 3),
            "mots": _time_words(beat, clock, duration),
        })
        clock += duration

        if progress:
            progress(index + 1, len(script.beats), clock)

    track = np.concatenate(pieces) if pieces else np.zeros(0, dtype="float32")
    _write_wav(audio_dir / "voix.wav", track, SAMPLE_RATE)

    return {
        # `source` dit d'où viennent les nombres, pas quel moteur a parlé.
        # Il valait « kokoro », du temps où il n'y avait qu'un moteur : un
        # fichier produit avec Edge annonçait donc Kokoro. Les trois
        # moteurs donnent des bornes de beat mesurées, donc la même qualité
        # temporelle, et c'est cela que ce champ décrit. Qui a parlé est
        # dans `voix.provider`, et nulle part ailleurs.
        "source": "mesure",
        "avertissement": (
            "Durées de beat mesurées sur l'audio réel. Position des mots à "
            "l'intérieur d'un beat répartie par syllabes : les coupes du "
            "montage sont exactes, les sous-titres sont au mot près."
        ),
        "voix": machine.fiche(),
        "duree_totale_s": round(len(track) / SAMPLE_RATE, 3),
        "nb_beats": len(entries),
        "nb_mots": sum(len(e["mots"]) for e in entries),
        "beats": entries,
    }
