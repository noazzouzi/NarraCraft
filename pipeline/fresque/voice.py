"""Synthèse de la voix, et l'alignement qui en découle.

**Un appel, un fichier.** La narration entière part en une fois, et ce qui
revient est écrit tel quel dans `voix.wav`. Le film est une prise : aucun
découpage, aucun rognage, aucun silence ajouté, aucune retouche.

Reste à savoir où commence chaque beat, puisque c'est là que le montage a
le droit de changer d'image. Le moteur le dit lui-même : Edge rend, dans le
même flux que l'audio, les bornes de chaque phrase qu'il prononce. On les
recoupe contre le texte envoyé, et on s'arrête si les deux divergent.

La position d'un mot *à l'intérieur* d'un beat reste répartie au poids
syllabique, jusqu'à ce que `fresque aligner` la mesure.
`narration.pause_phrase_s` et `pause_virgule_s` pondèrent cette
répartition : ce sont des valeurs relevées sur le moteur, et elles ne
produisent aucun son. `alignment.json` dit quelle méthode a servi, dans son
champ `source`.

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

Seul Edge rend ses bornes de phrase. Kokoro n'expose rien, et l'endpoint
ElevenLabs utilisé ici non plus : avec eux `voix.wav` est écrit, le
découpage reste inconnu, et `synthesize` renvoie vers `fresque aligner`.

POURQUOI UN SEUL APPEL
======================
Ce qui suit vient d'une mesure, après qu'un film entier a sonné mécanique.

Ce module a longtemps découpé chaque beat en phrases, appelé le moteur sur
chaque morceau, rogné son silence et recollé le tout autour d'un blanc
constant. Résultat mesuré sur `la-faillite-de-subway` : quarante-huit
pauses de 0,450 s au millième près, et un point qui durait exactement aussi
longtemps qu'une virgule. C'est ce qu'on entend comme « robotique ».

Un moteur en ligne sait lire un texte long. Sur un texte entier, Edge
laisse 0,35 s après une virgule et 1,28 s après un point, et son intonation
tient d'une phrase à l'autre. Il connaît la ponctuation mieux que nous, et
il est le seul à savoir ce qu'il vient de dire.
"""
from __future__ import annotations

import re
import unicodedata
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import config
from .align import syllables, _tokenize  # noqa: PLC2701 — same module family
from .script_parser import Script

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

#: Une phrase telle que le moteur dit l'avoir dite : son texte, et où elle
#: tombe dans l'audio qu'il vient de rendre. C'est de la donnée du
#: fournisseur, pas une mesure de notre part.
Phrase = tuple[str, float, float]


class Moteur:
    """Ce qu'un moteur de voix doit savoir faire : dire un texte.

    Un seul appel par film. `dire()` reçoit la narration entière et rend
    l'audio entier ; ce qu'il rend est écrit tel quel.

    `phrases` est ce que le moteur dit de sa propre sortie : où chaque
    phrase tombe dedans. Edge le donne, et c'est ce qui permet de savoir où
    commence chaque beat sans découper la narration en morceaux. Un moteur
    qui ne le donne pas laisse la liste vide, et `synthesize` le dit.
    """

    nom: str = ""

    @classmethod
    def catalogue(cls) -> list["Voix"]:  # pragma: no cover - interface
        """Les voix disponibles. Sans instancier le moteur : lister ne doit
        pas charger trois cents mégaoctets de modèle ni ouvrir de session."""
        raise NotImplementedError

    def dire(self, texte: str):  # pragma: no cover - interface
        raise NotImplementedError

    def phrases(self) -> list[Phrase]:
        """Les bornes du dernier `dire()`. Vide si le moteur n'en rend pas."""
        return []

    def fiche(self) -> dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError


class MoteurKokoro(Moteur):
    """Local, sans réseau, et sans bornes de phrase.

    Mesuré sur ff_siwis : 0,10 s après un point, à peine plus qu'après une
    virgule. Il ne dit pas non plus où tombent ses phrases, donc un film
    parlé par lui demande `fresque aligner` pour être monté.
    """

    nom = "kokoro"

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


#: Les offsets d'Edge sont en centaines de nanosecondes — l'unité de temps
#: de Windows, qui traverse l'API telle quelle.
_TICKS_PAR_SECONDE = 10_000_000


class MoteurEdge(Moteur):
    """Les voix neuronales de Microsoft Edge. Gratuites, sans clé, en ligne.

    Sa sortie est écrite telle quelle. Voir « ON NE RETOUCHE PAS LA SORTIE
    DU MOTEUR », en tête de module.
    """

    nom = "edge"

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
        self._phrases: list[Phrase] = []
        try:
            import edge_tts  # noqa: F401
            import soundfile  # noqa: F401
        except ImportError as error:  # pragma: no cover - environment dependent
            raise VoiceError(
                "edge-tts n'est pas installé : pip install edge-tts soundfile"
            ) from error

    def dire(self, texte: str):
        """Un appel, quelle que soit la longueur du texte.

        Le flux porte deux choses : les morceaux d'audio, et des évènements
        `SentenceBoundary` qui disent où chaque phrase tombe dedans. Les
        offsets sont en centaines de nanosecondes, l'unité de Windows.
        """
        import asyncio
        import io
        import os

        import edge_tts
        import soundfile as sf

        async def chercher() -> tuple[bytes, list[Phrase]]:
            # `proxy` sert les réseaux d'entreprise ; sans variable
            # d'environnement il vaut None et ne change rien.
            parole = edge_tts.Communicate(
                texte, self.voice, rate=self.rate,
                volume=self.volume, pitch=self.pitch,
                proxy=os.environ.get("HTTPS_PROXY"),
            )
            tampon = io.BytesIO()
            bornes: list[Phrase] = []
            async for morceau in parole.stream():
                if morceau["type"] == "audio":
                    tampon.write(morceau["data"])
                elif morceau["type"] in ("SentenceBoundary", "WordBoundary"):
                    debut = morceau["offset"] / _TICKS_PAR_SECONDE
                    duree = morceau["duration"] / _TICKS_PAR_SECONDE
                    bornes.append((morceau["text"], debut, debut + duree))
            return tampon.getvalue(), bornes

        brut, self._phrases = asyncio.run(chercher())
        if not brut:
            raise VoiceError(
                f"Edge n'a rien rendu pour « {texte[:40]}… » — "
                f"vérifier la voix `{self.voice}` et la connexion."
            )
        return sf.read(io.BytesIO(brut), dtype="float32", always_2d=False)

    def phrases(self) -> list[Phrase]:
        return list(self._phrases)

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

    Sa sortie est écrite telle quelle, comme celle d'Edge. Le point de
    terminaison utilisé ici ne rend pas les bornes de phrase (il en existe
    un, `with-timestamps`, qui les donnerait) : `phrases()` reste donc vide,
    et un film parlé par lui demande `fresque aligner` pour être monté.
    """

    nom = "elevenlabs"

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

        return sf.read(
            io.BytesIO(reponse.content), dtype="float32", always_2d=False)

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


def _time_words(texte: str, start: float, duration: float) -> list[dict[str, Any]]:
    """Spread a beat's words across its measured duration.

    Punctuation pauses are taken out first, then the remaining time is split
    between words in proportion to their syllable count.
    """
    words = _tokenize(texte)
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

def _lettres(texte: str) -> str:
    """Le texte réduit à ses lettres et ses chiffres, sans accent ni casse.

    Sert à reconnaître qu'une phrase rendue par le moteur est bien celle
    du script, malgré la ponctuation et les espaces qui diffèrent.
    """
    plat = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in plat if c.isalnum())


def _phrases_par_beat(
    script: Script, phrases: list[Phrase],
) -> list[list[Phrase]]:
    """Quelles phrases appartiennent à quel beat, d'après le moteur.

    Le moteur rend ses phrases dans l'ordre du texte qu'on lui a donné, et
    ce texte est la concaténation des beats. On avance donc en parallèle :
    on consomme des phrases jusqu'à avoir couvert les lettres du beat
    courant, et ses bornes sont celles de la première et de la dernière.

    Rien n'est mesuré ici, rien n'est deviné : ce sont les nombres du
    fournisseur, recoupés contre le texte qu'on lui a envoyé.
    """
    groupes: list[list[Phrase]] = []
    index = 0
    for beat in script.beats:
        vise = _lettres(beat.text)
        accumule = ""
        premier = index
        while index < len(phrases) and len(accumule) < len(vise):
            accumule += _lettres(phrases[index][0])
            index += 1
        if index == premier:
            raise VoiceError(
                f"{beat.id} : le moteur n'a rendu aucune phrase pour ce beat. "
                "Le texte envoyé et les bornes reçues ne concordent pas."
            )
        if accumule != vise:
            raise VoiceError(
                f"{beat.id} : le moteur n'a pas dit ce qu'on lui a donné.\n"
                f"  attendu : {vise[:60]}…\n"
                f"  rendu   : {accumule[:60]}…"
            )
        groupes.append(phrases[premier:index])

    if index != len(phrases):
        raise VoiceError(
            f"{len(phrases) - index} phrase(s) rendues en trop : le texte "
            "envoyé et le script ne correspondent pas."
        )
    return groupes


def synthesize(
    script: Script,
    audio_dir: Path,
    progress: Callable[[int, int, float], None] | None = None,
) -> dict[str, Any]:
    """Un appel au moteur, un fichier, et les bornes qu'il a données.

    La narration entière part en une fois. Ce qui revient est écrit tel
    quel dans `voix.wav` : aucun découpage, aucun rognage, aucun silence
    ajouté entre les beats ou entre les actes. Le film est une prise.

    Reste à savoir où commence chaque beat, puisque c'est là que le montage
    a le droit de changer d'image. Edge le dit lui-même, phrase par phrase,
    dans le même flux que l'audio. On ne mesure donc rien : on recoupe ce
    qu'il annonce contre le texte qu'on lui a envoyé (`_phrases_par_beat`),
    et si les deux ne concordent pas, on s'arrête plutôt que de deviner.

    Un moteur qui ne rend pas ses bornes — Kokoro, ElevenLabs — laisse le
    film sans découpage. Le fichier est là, le montage ne peut pas se
    faire : `fresque aligner` les retrouve par alignement forcé.
    """
    import numpy as np

    machine = moteur()
    # Le texte envoyé, et rien de plus : les beats séparés par une ligne
    # vide, comme des paragraphes. Le moteur y lira ses respirations.
    texte = "\n\n".join(beat.text for beat in script.beats)

    if progress:
        progress(0, len(script.beats), 0.0)
    samples, rate = machine.dire(texte)
    samples = np.asarray(samples, dtype="float32")
    if rate != SAMPLE_RATE:
        raise VoiceError(f"Fréquence inattendue : {rate} Hz (attendu {SAMPLE_RATE}).")

    _write_wav(audio_dir / "voix.wav", samples, rate)
    duree_totale = len(samples) / rate

    phrases = machine.phrases()
    if not phrases:
        raise VoiceError(
            f"{machine.nom} ne dit pas où tombent ses phrases, donc le "
            "découpage en beats est inconnu. `voix.wav` est écrit ; lancer "
            "`fresque aligner` pour retrouver les bornes, ou passer à un "
            "moteur qui les rend (`voix.provider: edge`)."
        )

    groupes = _phrases_par_beat(script, phrases)
    entries: list[dict[str, Any]] = []
    for index, (beat, dites) in enumerate(zip(script.beats, groupes)):
        # Le film commence au début du fichier : le moteur pose un dixième
        # de seconde avant le premier mot, et ce dixième appartient au film.
        debut = 0.0 if index == 0 else dites[0][1]
        # Le dernier beat va jusqu'au bout du fichier, pour la même raison :
        # le moteur arrête sa dernière phrase sur le dernier mot.
        fin = duree_totale if index == len(script.beats) - 1 else dites[-1][2]
        entries.append({
            "id": beat.id,
            "acte": beat.act,
            "debut_s": round(debut, 3),
            "fin_s": round(fin, 3),
            "duree_s": round(fin - debut, 3),
            "mots": _time_words(beat.text, debut, fin - debut),
        })
        if progress:
            progress(index + 1, len(script.beats), fin)

    return {
        # `source` dit d'où viennent les nombres, pas quel moteur a parlé.
        # Qui a parlé est dans `voix`, et nulle part ailleurs.
        "source": "mesure",
        "avertissement": (
            "Un seul appel au moteur, sa sortie écrite telle quelle. Bornes "
            "de beat données par le moteur, phrase par phrase. Position des "
            "mots à l'intérieur d'un beat répartie par syllabes — "
            "`fresque aligner` la mesure."
        ),
        "voix": machine.fiche(),
        "duree_totale_s": round(duree_totale, 3),
        "nb_beats": len(entries),
        "nb_mots": sum(len(e["mots"]) for e in entries),
        "nb_phrases": len(phrases),
        "beats": entries,
    }
