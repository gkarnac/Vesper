#!/usr/bin/env python3
"""
Narration des scènes — Vesper
=============================

Génère une piste MP3 par scène et par version (Nette / Brume) à partir des
fichiers story/chapitreN.js, avec Google Cloud TTS (même clé que Ma Vie).

    export GOOGLE_TTS_KEY='...'            (Windows : set GOOGLE_TTS_KEY=...)

    python3 narration.py --voix                    # liste les voix masculines fr-CA
    python3 narration.py --essai                   # un extrait par voix → audio/essais/
    python3 narration.py --chapitre 1              # tout le chapitre 1
    python3 narration.py --chapitre 1 --scene 5    # une seule scène
    python3 narration.py --chapitre 0 --voix-nom fr-CA-Chirp3-HD-Charon

Sortie : audio/ch<N>/s<NN>-nette.mp3 et s<NN>-brume.mp3 (le chapitre 0 n'a
qu'une version : nette). Les fichiers existants sont gardés ; --force les refait.

Ne jamais écrire la clé dans ce fichier : le dépôt est public.
Besoin de ffmpeg dans le PATH.
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOIX_DEFAUT = "fr-CA-Chirp3-HD-Charon"   # à remplacer par la voix choisie après --essai
DEBIT = 0.90                             # un peu lent : registre grave, posé (esprit Thief)
BITRATE = "64k"
SILENCE_DEBUT = 0.6                      # secondes avant la première phrase
SILENCE_PARA = 0.9                       # entre deux paragraphes


def cle():
    k = os.environ.get("GOOGLE_TTS_KEY")
    if not k:
        sys.exit("GOOGLE_TTS_KEY absente. Définis-la puis relance.")
    return k


def appel(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def run(args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def charger(n):
    src = open(os.path.join(RACINE, "story", f"chapitre{n}.js"), encoding="utf-8").read()
    return json.loads(src[src.index("{"):src.rindex("}") + 1])


def nettoyer(t):
    t = t.replace("*", "")
    t = re.sub(r"^—\s*", "", t)            # tiret de dialogue en début de paragraphe
    return t.strip()


def tts(texte, voix, sortie):
    payload = {"input": {"text": texte},
               "voice": {"languageCode": "fr-CA", "name": voix},
               "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000, "speakingRate": DEBIT}}
    r = appel("https://texttospeech.googleapis.com/v1/text:synthesize?key=" + cle(), payload)
    open(sortie, "wb").write(base64.b64decode(r["audioContent"]))


def silence(secs, sortie):
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(secs), sortie])


def piste(paras, voix, sortie):
    tmp = tempfile.mkdtemp()
    try:
        parts = [os.path.join(tmp, "d.wav")]
        silence(SILENCE_DEBUT, parts[0])
        sp = os.path.join(tmp, "sp.wav"); silence(SILENCE_PARA, sp)
        for i, p in enumerate(paras):
            f = os.path.join(tmp, f"p{i}.wav"); tts(nettoyer(p), voix, f)
            parts += [f, sp]
        lst = os.path.join(tmp, "l.txt")
        open(lst, "w").write("".join(f"file '{x}'\n" for x in parts))
        os.makedirs(os.path.dirname(sortie), exist_ok=True)
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-ar", "24000", "-ac", "1",
             "-b:a", BITRATE, sortie])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def voix_masculines():
    r = appel("https://texttospeech.googleapis.com/v1/voices?languageCode=fr-CA&key=" + cle())
    return sorted(v["name"] for v in r.get("voices", [])
                  if v["name"].startswith("fr-CA-Chirp3-HD") and v.get("ssmlGender") == "MALE")


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--voix", action="store_true", help="lister les voix masculines Chirp3-HD fr-CA")
    a.add_argument("--essai", action="store_true", help="un extrait par voix masculine")
    a.add_argument("--chapitre", type=int)
    a.add_argument("--scene", type=int)
    a.add_argument("--voix-nom", default=VOIX_DEFAUT)
    a.add_argument("--force", action="store_true")
    o = a.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg introuvable dans le PATH.")

    if o.voix:
        print("\n".join(voix_masculines())); return

    if o.essai:
        ch = charger(1); sc = ch["scenes"][0]
        for v in voix_masculines():
            f = os.path.join(RACINE, "audio", "essais", v + ".mp3")
            piste(sc["paras"][:1], v, f); print("ok", f)
        return

    if o.chapitre is None:
        a.error("--chapitre requis (ou --voix / --essai)")
    ch = charger(o.chapitre)
    for sc in ch["scenes"]:
        if o.scene and sc["n"] != o.scene:
            continue
        versions = [("nette", sc["paras"])] + ([("brume", sc["brume"])] if sc.get("brume") else [])
        for nom, paras in versions:
            f = os.path.join(RACINE, "audio", f"ch{ch['id']}", f"s{sc['n']:02d}-{nom}.mp3")
            if os.path.exists(f) and not o.force:
                print("garde", f); continue
            piste(paras, o.voix_nom, f); print("ok   ", f)


if __name__ == "__main__":
    main()
