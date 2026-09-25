"""Parse 02-script.md into beats.

The format documented in the fresque-script skill is a contract: beats are
`### Bnnn` headings, each carrying exactly one `> intention:` line, and the
body holds only spoken text. This parser enforces that contract and fails
loudly rather than silently mangling a malformed script.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ACT_RE = re.compile(r"^##\s+Acte\s+([IVXLC\d]+)\s*[—–-]\s*(.+?)\s*$")
BEAT_RE = re.compile(r"^###\s+(B\d{3})\s*$")
INTENT_RE = re.compile(r"^>\s*intention\s*:\s*(.+?)\s*$", re.IGNORECASE)
#: Optional. Marks a beat as a change of state — a revelation, an open
#: question, a change of scale. Nothing in the spoken text lets a machine
#: recognise one, so the writer declares it and the lint checks the spacing.
RELANCE_RE = re.compile(r"^>\s*relance\s*:\s*(.+?)\s*$", re.IGNORECASE)
HEADING_RE = re.compile(r"^#{1,6}\s")

#: Le tableau de fin de fichier. Toutes les métadonnées de contrôle y sont
#: rassemblées — lien, boucle, relance — plutôt que dispersées en lignes
#: `>` au-dessus de chaque beat. Un checkpoint se lit mieux quand la
#: narration reste nue et que la mécanique tient sur un seul tableau.
CONTROLE_RE = re.compile(r"^##\s+Contr[oô]le\s*$", re.IGNORECASE)
LIGNE_CONTROLE_RE = re.compile(r"^\|(.+)\|\s*$")
BOUCLE_RE = re.compile(
    r"^(ouvre|ferme)\s+(L\d+)\s*(?:[—–-]\s*(.*))?$", re.IGNORECASE)
LIENS = ("donc", "mais")

# Stage directions that must never reach the speech synthesiser.
STAGE_DIRECTION_RE = re.compile(r"[\[\](){}]|^\s*[-*]\s")


class ScriptError(ValueError):
    """Raised when 02-script.md violates the format contract."""


@dataclass
class Beat:
    id: str
    act: str
    act_title: str
    intention: str
    text: str
    line: int = 0
    #: Non-empty when this beat is declared a retention beat, and saying what
    #: kind. See RELANCE_RE.
    relance: str = ""
    #: `donc` ou `mais` — comment ce beat s'enchaîne au précédent. Vide pour
    #: le premier, et pour un script qui n'a pas de tableau de contrôle.
    lien: str = ""

    @property
    def word_count(self) -> int:
        return len(re.findall(r"\b[\w'’-]+\b", self.text, re.UNICODE))


@dataclass
class Boucle:
    """Une question posée à un beat, répondue à un autre.

    C'est la seule chose qui fait attendre un spectateur plusieurs minutes.
    Aucune machine ne peut la reconnaître dans le texte — un fait dont la
    cause manque et un fait ordinaire sont les mêmes mots — donc l'auteur la
    déclare, et le lint vérifie qu'elle se ferme, et assez tard.
    """
    nom: str
    question: str = ""
    ouvre: str = ""
    ferme: str = ""


@dataclass
class Script:
    title: str
    beats: list[Beat] = field(default_factory=list)
    boucles: list[Boucle] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return sum(b.word_count for b in self.beats)


def parse(path: Path) -> Script:
    lines = path.read_text(encoding="utf-8").splitlines()

    title = ""
    act = act_title = ""
    script = Script(title="")
    current: Beat | None = None
    body: list[str] = []

    def close_beat() -> None:
        nonlocal current, body
        if current is None:
            return
        text = "\n".join(body).strip()
        if not text:
            raise ScriptError(f"{current.id} n'a aucun texte de narration.")
        if not current.intention:
            raise ScriptError(
                f"{current.id} n'a pas de ligne `> intention:` (obligatoire)."
            )
        current.text = text
        script.beats.append(current)
        current, body = None, []

    controle: list[tuple[int, list[str]]] = []
    dans_controle = False

    for number, raw in enumerate(lines, start=1):
        line = raw.rstrip()

        if not title and line.startswith("# "):
            title = line[2:].strip()
            continue

        if CONTROLE_RE.match(line):
            close_beat()
            dans_controle = True
            continue

        if dans_controle:
            if HEADING_RE.match(line):
                dans_controle = False
            else:
                cellules = LIGNE_CONTROLE_RE.match(line)
                if cellules:
                    controle.append(
                        (number, [c.strip() for c in cellules.group(1).split("|")]))
                continue

        act_match = ACT_RE.match(line)
        if act_match:
            close_beat()
            act, act_title = act_match.group(1), act_match.group(2)
            continue

        beat_match = BEAT_RE.match(line)
        if beat_match:
            close_beat()
            current = Beat(
                id=beat_match.group(1), act=act, act_title=act_title,
                intention="", text="", line=number,
            )
            continue

        if current is None:
            continue

        # Any other heading ends the beat (e.g. the trailing `## Contrôle`).
        if HEADING_RE.match(line):
            close_beat()
            continue

        intent_match = INTENT_RE.match(line)
        if intent_match:
            if current.intention:
                raise ScriptError(
                    f"{current.id} a plusieurs lignes `> intention:` "
                    "(une seule, sur une seule ligne)."
                )
            current.intention = intent_match.group(1)
            continue

        relance_match = RELANCE_RE.match(line)
        if relance_match:
            current.relance = relance_match.group(1)
            continue

        if line.strip() == "---":
            close_beat()
            continue

        if line.strip():
            if STAGE_DIRECTION_RE.search(line):
                raise ScriptError(
                    f"{current.id} ligne {number} : le corps d'un beat ne "
                    "contient que le texte prononcé. Crochets, parenthèses "
                    "et listes partiraient tels quels dans la voix.\n"
                    f"  → {line.strip()}"
                )
            body.append(line.strip())

    close_beat()
    script.title = title or path.stem
    _lire_controle(script, controle)

    _validate(script)
    return script


def _lire_controle(script: Script, lignes: list[tuple[int, list[str]]]) -> None:
    """Range le tableau de contrôle dans les beats et les boucles.

    Le tableau est optionnel : un script écrit avant qu'il existe se lit
    toujours. C'est le lint qui le réclame, parce que c'est lui qui sait
    quoi en faire.
    """
    par_id = {beat.id: beat for beat in script.beats}
    boucles: dict[str, Boucle] = {}

    for numero, cellules in lignes:
        identifiant = cellules[0]
        if not BEAT_RE.match(f"### {identifiant}"):
            continue  # en-tête du tableau, ou ligne de séparation
        beat = par_id.get(identifiant)
        if beat is None:
            raise ScriptError(
                f"ligne {numero} : le tableau de contrôle nomme {identifiant}, "
                "qui n'est pas un beat du script."
            )
        lien = cellules[1].lower() if len(cellules) > 1 else ""
        if lien in LIENS:
            beat.lien = lien
        elif lien and lien not in ("—", "-", "–"):
            raise ScriptError(
                f"{identifiant} : lien {lien!r} — attendu « donc » ou « mais ». "
                "Un beat qui ne peut dire que « et » est un élément de liste : "
                "le fusionner ou le couper."
            )

        brut = cellules[2] if len(cellules) > 2 else ""
        marque = BOUCLE_RE.match(brut)
        if marque:
            sens, nom, question = marque.group(1).lower(), marque.group(2).upper(), \
                (marque.group(3) or "").strip()
            boucle = boucles.setdefault(nom, Boucle(nom=nom))
            if sens == "ouvre":
                boucle.ouvre, boucle.question = identifiant, question or boucle.question
            else:
                boucle.ferme = identifiant
        elif brut:
            raise ScriptError(
                f"{identifiant} : boucle {brut!r} — attendu « ouvre L<n> — "
                "<question> » ou « ferme L<n> »."
            )

        if len(cellules) > 3 and cellules[3] and not beat.relance:
            beat.relance = cellules[3]

    script.boucles = [boucles[nom] for nom in sorted(boucles)]


def _validate(script: Script) -> None:
    if not script.beats:
        raise ScriptError(
            "Aucun beat trouvé. Format attendu : `### B001` suivi d'une "
            "ligne `> intention:` puis du texte."
        )

    seen: set[str] = set()
    for index, beat in enumerate(script.beats, start=1):
        if beat.id in seen:
            raise ScriptError(f"Beat {beat.id} en double.")
        seen.add(beat.id)
        expected = f"B{index:03d}"
        if beat.id != expected:
            raise ScriptError(
                f"Numérotation discontinue : {expected} attendu, "
                f"{beat.id} trouvé (ligne {beat.line}). Les beats sont "
                "numérotés en continu à travers tout le document."
            )
