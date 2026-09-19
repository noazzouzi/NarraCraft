"""Synthesise the transition sounds, locally and from nothing.

A cut without sound reads as a slideshow advancing. The same cut with a
short whoosh under it reads as an edit. It is the cheapest improvement
available to this pipeline, and it costs exactly zero: these are a few
seconds of shaped noise, computed here rather than downloaded.

Downloading them would mean a licence to track for every sound, a host that
may disappear, and a network round trip in a step that has no other reason
to touch the network. Generating them means the files are reproducible from
the code that made them, and identical on every machine.

Nothing here is random in the free sense: every waveform is derived from a
fixed seed, so a rebuild produces byte-identical files and a re-render is
not gratuitously different from the one before it.
"""
from __future__ import annotations

import wave
from pathlib import Path

#: 44.1 kHz because these carry energy up to the top of the audible band —
#: the voice track's 24 kHz would fold a whoosh's air back down as a hiss.
RATE = 44_100

#: Every sound this module can make, and what it is for. The timeline maps
#: a transition to one of these names; nothing else may invent one.
SONS = ("souffle", "souffle_inverse", "impact", "sub")


def _envelope(n: int, attack: float, decay: float, np) -> "np.ndarray":
    """Attack/decay shape, both in fractions of the total length."""
    t = np.linspace(0.0, 1.0, n, dtype="float64")
    montee = np.clip(t / max(attack, 1e-6), 0.0, 1.0)
    chute = np.clip((1.0 - t) / max(decay, 1e-6), 0.0, 1.0)
    return montee * chute**1.8


def _noise(n: int, np) -> "np.ndarray":
    # A fixed seed: a rebuild must produce the same file, or every render
    # differs from the last for no reason anyone asked for.
    return np.random.default_rng(20260919).standard_normal(n)


def _sweep(samples: "np.ndarray", start_hz: float, end_hz: float, np) -> "np.ndarray":
    """Run a one-pole low-pass whose cutoff glides from start to end.

    A moving filter over noise is what a whoosh actually is: the pitch does
    not change, the part of the spectrum you hear does. Done with a fixed
    cutoff it sounds like a hiss, which is the difference between an edit
    and a tape fault.
    """
    n = len(samples)
    cutoff = np.linspace(start_hz, end_hz, n)
    # Per-sample smoothing coefficient of a one-pole filter at that cutoff.
    alpha = 1.0 - np.exp(-2.0 * np.pi * cutoff / RATE)

    out = np.empty(n, dtype="float64")
    etat = 0.0
    for i in range(n):
        etat += alpha[i] * (samples[i] - etat)
        out[i] = etat
    return out


def souffle(duree_s: float = 0.42, inverse: bool = False) -> "np.ndarray":
    """The whoosh that leads a cut.

    Forwards it opens up — dull to bright — and lands on the cut. Reversed
    it closes down, which is what a sideways slide wants underneath it.
    """
    import numpy as np

    n = int(RATE * duree_s)
    brut = _noise(n, np)
    bas, haut = (5200.0, 400.0) if inverse else (400.0, 5200.0)
    filtre = _sweep(brut, bas, haut, np)

    forme = _envelope(n, 0.12 if not inverse else 0.45, 0.55, np)
    signal = filtre * forme
    # Normalised here, levelled by the timeline's gain. A sound that arrives
    # at its own arbitrary loudness cannot be balanced against the voice.
    return signal / (np.abs(signal).max() or 1.0)


def impact(duree_s: float = 0.85) -> "np.ndarray":
    """A low hit, for an act boundary.

    A sine falling from 90 Hz to 38 Hz, with a short noise transient on top
    so it has an edge to arrive on. Without the transient it is felt but not
    heard, and it disappears entirely on a phone speaker.
    """
    import numpy as np

    n = int(RATE * duree_s)
    t = np.arange(n, dtype="float64") / RATE

    # Instantaneous phase of a falling pitch: integrate the frequency ramp,
    # don't multiply by t, or the pitch bends in the wrong direction.
    freq = 90.0 * np.exp(-t * 2.2) + 38.0
    corps = np.sin(2.0 * np.pi * np.cumsum(freq) / RATE)
    corps *= np.exp(-t * 4.5)

    bord = int(RATE * 0.05)
    transitoire = np.zeros(n)
    transitoire[:bord] = _sweep(_noise(bord, np), 3000.0, 700.0, np)
    transitoire[:bord] *= np.exp(-np.linspace(0, 6, bord))

    signal = corps + 0.42 * transitoire
    return signal / (np.abs(signal).max() or 1.0)


def sub(duree_s: float = 1.4) -> "np.ndarray":
    """A sub drop, for the opening shot and nothing else.

    Almost inaudible as a pitch, entirely audible as a presence. Used more
    than once per film it stops meaning anything.
    """
    import numpy as np

    n = int(RATE * duree_s)
    t = np.arange(n, dtype="float64") / RATE
    freq = 55.0 * np.exp(-t * 1.1) + 26.0
    signal = np.sin(2.0 * np.pi * np.cumsum(freq) / RATE) * np.exp(-t * 1.6)
    # A soft start: a sub that begins at full amplitude clicks.
    signal[: int(RATE * 0.03)] *= np.linspace(0, 1, int(RATE * 0.03))
    return signal / (np.abs(signal).max() or 1.0)


def _write(path: Path, samples, np) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(np.asarray(samples, dtype="float32"), -1.0, 1.0)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(RATE)
        fh.writeframes((pcm * 32767).astype("<i2").tobytes())


def build(directory: Path, force: bool = False) -> dict[str, str]:
    """Write every sound into `directory`, and return {name: relative path}.

    Idempotent: a file already there is kept, because rewriting it would
    make Remotion re-copy it into its bundle for no reason.
    """
    import numpy as np

    generateurs = {
        "souffle": lambda: souffle(),
        "souffle_inverse": lambda: souffle(inverse=True),
        "impact": impact,
        "sub": sub,
    }

    produced: dict[str, str] = {}
    for name, make in generateurs.items():
        path = directory / f"{name}.wav"
        if force or not path.is_file():
            _write(path, make(), np)
        produced[name] = path.name
    return produced


# --- Musique de fond ---------------------------------------------------------
#
# Un lit sonore, pas une musique. Il n'a ni rythme ni mélodie, parce que tout
# ce qui en a entre en concurrence avec la voix off : le spectateur suit l'un
# ou l'autre, jamais les deux. Ce qu'on cherche est l'inverse — quelque chose
# qu'on ne remarque qu'en l'enlevant.
#
# Synthétisée ici pour les mêmes raisons que les transitions : aucune licence
# à suivre, aucun hôte qui disparaît, un fichier identique d'une machine à
# l'autre. Une piste téléchargée « libre de droit » demande de vérifier sa
# licence, de la stocker, et de la re-vérifier à chaque publication.

#: Intervalles en demi-tons, depuis la tonique. Le mode change le caractère
#: du lit sans rien changer au code — c'est ce qui permet à un template de
#: sonner autrement qu'un autre.
#
#: Les partiels montent jusqu'à deux octaves et demie au-dessus de la
#: tonique, et ce n'est pas un choix musical mais un choix de restitution.
#: Un lit qui vit sous 250 Hz est mesurable et inaudible : ni un
#: haut-parleur d'ordinateur ni celui d'un téléphone ne descend là. La
#: première version s'arrêtait à l'octave-quinte et n'avait que onze pour
#: cent de son énergie dans la bande que tout le monde restitue.
MODES = {
    # Mineur sans tierce : ouvert, ne raconte rien de lui-même.
    "sobre": (0, 7, 12, 19, 24, 31),
    # Tierce mineure ajoutée : nettement plus sombre.
    "sombre": (0, 3, 7, 12, 15, 24, 27),
    # Quarte et quinte : tendu, sans être triste.
    "tendu": (0, 5, 7, 12, 17, 24, 29),
    # Tierce majeure : ouvert, presque serein.
    "clair": (0, 4, 7, 12, 16, 24, 28),
}


def musique(duree_s: float = 40.0, tonique_hz: float = 55.0,
            mode: str = "sobre") -> "np.ndarray":
    """Un bourdon bouclable, de `duree_s` secondes.

    La boucle est sans couture par construction : chaque partiel et chaque
    oscillation lente compte un nombre **entier** de cycles sur la durée
    totale. Un fondu croisé aux extrémités marcherait aussi, mais il laisse
    une respiration audible toutes les quarante secondes, et sur un quart
    d'heure elle devient le seul événement de la bande.
    """
    import numpy as np

    if mode not in MODES:
        raise ValueError(
            f"mode musical {mode!r} inconnu (attendu : {', '.join(MODES)})"
        )

    n = int(RATE * duree_s)
    t = np.arange(n, dtype="float64") / RATE
    base = 1.0 / duree_s  # fréquence dont toutes les autres sont multiples

    melange = np.zeros(n)
    for rang, demi_tons in enumerate(MODES[mode]):
        cible = tonique_hz * 2 ** (demi_tons / 12)
        # Ramenée au multiple entier le plus proche de la fondamentale de la
        # boucle : c'est ce qui rend le raccord inaudible.
        freq = max(round(cible / base), 1) * base

        # Les partiels aigus s'effacent, mais doucement — en fonction de leur
        # hauteur et non de leur rang. La première version les divisait par
        # leur rang, ce qui écrasait précisément ceux qui rendent le lit
        # audible sur un petit haut-parleur.
        poids = (tonique_hz / freq) ** 0.35

        # Deux voix légèrement désaccordées par partiel. Le battement lent
        # qui en résulte est ce qui empêche le lit de sonner comme une
        # tonalité de test.
        voix = np.zeros(n)
        for ecart in (-1.0, 1.0):
            detune = max(round((freq + ecart * base) / base), 1) * base
            voix += np.sin(2.0 * np.pi * detune * t + rang * 1.7)

        # Chaque partiel respire à son propre rythme, en cycles entiers lui
        # aussi. Décalés, ils font que l'accord ne se présente jamais deux
        # fois dans le même équilibre.
        cycles = 1 + rang
        respiration = 0.72 + 0.28 * np.sin(2.0 * np.pi * cycles * base * t + rang)
        melange += poids * voix * respiration

    # Enveloppe d'ensemble : une houle très lente, deux cycles par boucle.
    houle = 0.82 + 0.18 * np.sin(2.0 * np.pi * 2 * base * t)
    melange *= houle

    # Un plancher de bruit filtré très bas, pour l'air. Sans lui le bourdon
    # sonne synthétique ; avec, il a une pièce autour de lui.
    air = _sweep(_noise(n, np), 220.0, 220.0, np)
    melange += 0.05 * air / (np.abs(air).max() or 1.0)

    return melange / (np.abs(melange).max() or 1.0)


def build_musique(destination: Path, duree_s: float = 40.0,
                  tonique_hz: float = 55.0, mode: str = "sobre",
                  force: bool = False) -> Path:
    """Écrit la boucle si elle n'existe pas déjà."""
    import numpy as np

    if force or not destination.is_file():
        _write(destination, musique(duree_s, tonique_hz, mode), np)
    return destination


def _ponderation_a(freq):
    """Réponse de la courbe A, qui approche la sensibilité de l'oreille.

    Elle chute très vite dans le grave : à 50 Hz elle retire une trentaine
    de décibels. C'est ce qui rend un bourdon très grave mesurable et
    pourtant inaudible — et c'est l'erreur qu'on a faite en réglant le lit
    à l'œil sur un spectre plutôt qu'à l'oreille sur un niveau.
    """
    import numpy as np

    f = np.maximum(np.asarray(freq, dtype="float64"), 1e-6)
    numerateur = (12194.0**2) * f**4
    denominateur = (
        (f**2 + 20.6**2)
        * np.sqrt((f**2 + 107.7**2) * (f**2 + 737.9**2))
        * (f**2 + 12194.0**2)
    )
    return numerateur / denominateur


def niveau_pondere_a(echantillons, rate: int = RATE) -> float:
    """Niveau perçu d'un signal, pondéré A.

    C'est la seule mesure qui répond à « est-ce qu'on l'entend ». Le niveau
    brut, lui, dit seulement qu'il y a de l'énergie quelque part.
    """
    import numpy as np

    x = np.asarray(echantillons, dtype="float64")
    if not len(x):
        return 0.0
    spectre = np.abs(np.fft.rfft(x))
    freqs = np.fft.rfftfreq(len(x), 1.0 / rate)
    return float(np.sqrt(((spectre * _ponderation_a(freqs)) ** 2).sum()) / len(x))


def lire_wav(chemin: Path) -> tuple["np.ndarray", int]:
    import numpy as np

    with wave.open(str(chemin)) as fh:
        rate = fh.getframerate()
        brut = fh.readframes(fh.getnframes())
    return np.frombuffer(brut, dtype="<i2").astype("float64") / 32768.0, rate


def gain_pour(musique_path: Path, voix_path: Path, niveau_db: float) -> float:
    """Le gain qui place le lit `niveau_db` sous la voix, à l'oreille.

    Régler ce gain à la main revient à deviner : le même 0,06 est inaudible
    sur un bourdon à 49 Hz et envahissant sur un lit à 300 Hz. On mesure les
    deux pistes et on résout.
    """
    musique_x, musique_r = lire_wav(musique_path)
    voix_x, voix_r = lire_wav(voix_path)

    niveau_musique = niveau_pondere_a(musique_x, musique_r)
    # Une minute de voix suffit à en établir le niveau, et c'est cent fois
    # plus rapide qu'une transformée sur un quart d'heure.
    niveau_voix = niveau_pondere_a(voix_x[: voix_r * 60], voix_r)
    if niveau_musique <= 0:
        return 0.0
    return float(10.0 ** (niveau_db / 20.0) * niveau_voix / niveau_musique)
