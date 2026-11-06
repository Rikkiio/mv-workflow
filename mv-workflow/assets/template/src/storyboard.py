"""The cut. Each build_*() returns a Timeline of back-to-back shots; render.py picks one with MM_BUILD (default:
build). Write shots in src/shots/ (shots/demo.py is a starting point) and lay them out here on the beat grid
(B(n) / bar(n) from mm.anim) once work/audio.json exists. Keep the old build functions when you make a new version."""
from mm.timeline import Timeline
from shots.demo import Demo


def build():
    return Timeline([Demo(0.0, 8.0)])
