#!/usr/bin/env python3

# VapourSynth Scene Detection
# Copyright (c) Akatsumekusa and contributors

# ---------------------------------------------------------------------
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# ---------------------------------------------------------------------


import argparse
from itertools import islice
import json
import math
import numpy as np
from pathlib import Path
from time import time
import vapoursynth as vs
from vapoursynth import core

parser = argparse.ArgumentParser(prog="VapourSynth Scene Detection", description="Detect scenes for av1an encoding", add_help=False)
parser.add_argument("-h", "--help", action="store_true", help="Display help and guide for VapourSynth Scene Detection")
parser.add_argument("-i", "--input", type=Path, help="Source video file")
parser.add_argument("--input-colour-range", choices=["limited", "full"], default="limited", help="The colour range for the source video file")
parser.add_argument("-m", "--method", choices=["wwxd", "wwxd_scxvid"], default="wwxd_scxvid", help="The method for scene detection. Using both WWXD and Scxvid is more reliable (Default), while WWXD alone is significantly faster")
parser.add_argument("--extra-split", default=264, help="Maximum length for a scene (Default: 264)")
parser.add_argument("--min-scene-len", default=12, help="Minimum length for a scene (Default: 12). Set this to match the length of the shortest cut in the source")
parser.add_argument("--target-split", default=60, help="Target length for a scene (Default: 60). More explained below")
parser.add_argument("-o", "--output-zones", type=Path, help="Output zones file for encoding")
parser.add_argument("--output-scenes", type=Path, help="Output scenes file for encoding")
args = parser.parse_args()
if args.help:
    parser.print_help()
    print("""
In the grand scheme of scene detection, av1an `--sc-method standard` is the more universal option for scene detection. It has multiple unique optimisations and is tested to work well in most conditions.

However, it has one big problem: av1an often prefers to place the keyframe at the start of a series of still, unmoving frames. This preference even takes priority over placing keyframes at actual scene changes. For most works, it's common to find cuts where the character will make some movements at the very start of a cut, before they stops moving and starts talking. Using av1an, these few frames will be allocated to the previous scenes. These are a low number of frames, with movements, and after an actual scene changes, but placed at the very end of previous scene, which is why they will often be encoded horrendously. Compared to av1an, WWXD or Scxvid is more reliable in this matter, and would have less issues like this.

A caveat is that WWXD and Scxvid struggles greatly in sections challenging for scene detection such as a continuous cut, many times the length of `scene_detection_extra_split`, featuring lots of movements but no actual scenecuts, or sections with a lot of very fancy transition effects between cuts. WWXD and Scxvid will mark either too much or too few keyframes. This is largely alleviated by the additional scene detection logic in this script, but you should still prefer av1an `--sc-method standard` in sources with such sections.

To deal with WWXD and Scxvid flagging too much scenechanges in complex everchanging sections, this script offers the `--target-split` option. This option marks the length for a scene for the scene detection mechanism to stop dividing it any further. However, this does not mean there won't be scenes shorter than this option. It's likely that scenes longer than the this option will be divided into scenes that are shorter than this option. The hard limit is still specified by `--min-scene-len`. Also, this option only affects sections where there are a lot of scenechanges detected by WWXD. For calmer sections where WWXD doesn't flag any scenechanges, the scene detection mechanism will only attempt to divide a scene if it is longer than `--extra-split`, and this option has no effects.""")
    raise SystemExit(0)
input_file = args.input
if not input_file:
    parser.print_usage()
    print("VapourSynth Scene Detection: error: the following arguments are required: -i/--input")
    raise SystemExit(2)
scene_detection_colour_range = args.input_colour_range
scene_detection_vapoursynth_method = args.method
scene_detection_extra_split = args.extra_split
scene_detection_min_scene_len = args.min_scene_len
scene_detection_target_split = args.target_split
zones_file = args.output_zones
scenes_file = args.output_scenes
if not zones_file and not scenes_file:
    parser.print_usage()
    print("VapourSynth Scene Detection: error: at least one of the following arguments is required: -o/--output-zones, --output-scenes")
    raise SystemExit(2)


# Scene detection
if True:
    if True:
        assert scene_detection_extra_split >= scene_detection_min_scene_len * 2, "`scene_detection_method` `vapoursynth` does not support `scene_detection_extra_split` to be smaller than 2 times `scene_detection_min_scene_len`."
    
        scene_detection_clip = core.lsmas.LWLibavSource(input_file.expanduser().resolve(), cache=0)
        scene_detection_bits = scene_detection_clip.format.bits_per_sample
        scene_detection_clip = scene_detection_clip.std.PlaneStats(scene_detection_clip[0] + scene_detection_clip, plane=0, prop="Luma")
        target_width = np.round(np.sqrt(1280 * 720 / scene_detection_clip.width / scene_detection_clip.height) * scene_detection_clip.width / 40) * 40
        if target_width < scene_detection_clip.width * 0.9:
            target_height = np.ceil(target_width / scene_detection_clip.width * scene_detection_clip.height / 2) * 2
            src_height = target_height / target_width * scene_detection_clip.width
            src_top = (scene_detection_clip.height - src_height) / 2
            scene_detection_clip = scene_detection_clip.resize.Point(width=target_width, height=target_height, src_top=src_top, src_height=src_height,
                                                                     format=vs.YUV420P8, dither_type="none")
        scene_detection_clip = scene_detection_clip.wwxd.WWXD()
        try:
            if scene_detection_vapoursynth_method == "wwxd_scxvid":
                scene_detection_clip = scene_detection_clip.scxvid.Scxvid()
        except NameError:
            assert False, "You need to select a `scene_detection_vapoursynth_method` to use `scene_detection_method` `vapoursynth`. Please check your config inside `Progression-Boost.py`."

        scene_detection_rjust_digits = math.floor(np.log10(scene_detection_clip.num_frames)) + 1
        scene_detection_rjust = lambda frame: str(frame).rjust(scene_detection_rjust_digits)
        
        scenes = {}
        scenes["frames"] = scene_detection_clip.num_frames
        scenes["scenes"] = []

        diffs = np.empty((scene_detection_clip.num_frames,), dtype=float)
        diffs[0] = 1.0
        luma_scenecut_prev = True
        def scene_detection_split_scene(great_diffs, diffs, start_frame, end_frame):
            print(f"\033[KFrame [{scene_detection_rjust(start_frame)}:{scene_detection_rjust(end_frame)}] / Creating scenes", end="\r")

            if end_frame - start_frame <= scene_detection_target_split or \
               end_frame - start_frame < 2 * scene_detection_min_scene_len:
                return [start_frame]

            great_diffs_sort = np.argsort(great_diffs)[::-1]

            if end_frame - start_frame <= 2 * scene_detection_target_split:
                for current_frame in great_diffs_sort:
                    if great_diffs[current_frame] < 1.16:
                        break
                    if current_frame - start_frame >= scene_detection_min_scene_len and end_frame - current_frame >= scene_detection_min_scene_len and \
                       current_frame - start_frame <= scene_detection_target_split and end_frame - current_frame <= scene_detection_target_split:
                        return scene_detection_split_scene(great_diffs, diffs, start_frame, current_frame) + \
                               scene_detection_split_scene(great_diffs, diffs, current_frame, end_frame)

            if end_frame - start_frame <= scene_detection_extra_split:
                for current_frame in great_diffs_sort:
                    if great_diffs[current_frame] < 1.16:
                        break
                    if (current_frame - start_frame >= scene_detection_min_scene_len and end_frame - current_frame >= scene_detection_min_scene_len) and \
                       (current_frame - start_frame <= scene_detection_target_split or end_frame - current_frame <= scene_detection_target_split):
                        return scene_detection_split_scene(great_diffs, diffs, start_frame, current_frame) + \
                               scene_detection_split_scene(great_diffs, diffs, current_frame, end_frame)

                for current_frame in great_diffs_sort:
                    if great_diffs[current_frame] < 1.16:
                        return [start_frame]
                    if current_frame - start_frame >= scene_detection_min_scene_len and end_frame - current_frame >= scene_detection_min_scene_len:
                        return scene_detection_split_scene(great_diffs, diffs, start_frame, current_frame) + \
                               scene_detection_split_scene(great_diffs, diffs, current_frame, end_frame)

            else: # end_frame - start_frame > scene_detection_extra_split
                for current_frame in great_diffs_sort:
                    if great_diffs[current_frame] < 1.12:
                        break
                    if (current_frame - start_frame >= scene_detection_min_scene_len and end_frame - current_frame >= scene_detection_min_scene_len) and \
                       math.ceil((current_frame - start_frame) / scene_detection_extra_split) + \
                       math.ceil((end_frame - current_frame) / scene_detection_extra_split) <= \
                       math.ceil((end_frame - start_frame) / scene_detection_extra_split + 0.15):
                        return scene_detection_split_scene(great_diffs, diffs, start_frame, current_frame) + \
                               scene_detection_split_scene(great_diffs, diffs, current_frame, end_frame)
                               
                for current_frame in great_diffs_sort:
                    if great_diffs[current_frame] < 1.16:
                        break
                    if (current_frame - start_frame >= scene_detection_min_scene_len and end_frame - current_frame >= scene_detection_min_scene_len) and \
                       (current_frame - start_frame <= scene_detection_target_split or end_frame - current_frame <= scene_detection_target_split):
                        return scene_detection_split_scene(great_diffs, diffs, start_frame, current_frame) + \
                               scene_detection_split_scene(great_diffs, diffs, current_frame, end_frame)

                for current_frame in great_diffs_sort:
                    if great_diffs[current_frame] < 1.16:
                        break
                    if current_frame - start_frame >= scene_detection_min_scene_len and end_frame - current_frame >= scene_detection_min_scene_len:
                        return scene_detection_split_scene(great_diffs, diffs, start_frame, current_frame) + \
                               scene_detection_split_scene(great_diffs, diffs, current_frame, end_frame)

                diffs_sort = np.argsort(diffs, stable=True)[::-1]

                for current_frame in diffs_sort:
                    if (current_frame - start_frame >= scene_detection_min_scene_len and end_frame - current_frame >= scene_detection_min_scene_len) and \
                       math.ceil((current_frame - start_frame) / scene_detection_extra_split) + \
                       math.ceil((end_frame - current_frame) / scene_detection_extra_split) <= \
                       math.ceil((end_frame - start_frame) / scene_detection_extra_split):
                        return scene_detection_split_scene(great_diffs, diffs, start_frame, current_frame) + \
                               scene_detection_split_scene(great_diffs, diffs, current_frame, end_frame)

            assert False, "This indicates a bug in the original code. Please report this to the repository including this error message in full."

        start = time() - 0.000001
        for current_frame, frame in islice(enumerate(scene_detection_clip.frames(backlog=48)), 1, None):
            print(f"\033[KFrame {current_frame} / Detecting scenes / {current_frame / (time() - start):.02f} fps", end="\r")

            if scene_detection_vapoursynth_method == "wwxd":
                scene_detection_scenecut = frame.props["Scenechange"] == 1
            elif scene_detection_vapoursynth_method == "wwxd_scxvid":
                scene_detection_scenecut = (frame.props["Scenechange"] == 1) + (frame.props["_SceneChangePrev"] == 1) / 2
            else:
                assert False, "Invalid `scene_detection_vapoursynth_method`. Please check your config inside `Progression-Boost.py`."
            if scene_detection_colour_range == "limited":
                if not luma_scenecut_prev:
                    luma_scenecut = frame.props["LumaMin"] > 231.125 * 2 ** (scene_detection_bits - 8) or \
                                    frame.props["LumaMax"] < 19.875 * 2 ** (scene_detection_bits - 8)
                else:
                    luma_scenecut = frame.props["LumaMin"] > 229.125 * 2 ** (scene_detection_bits - 8) or \
                                    frame.props["LumaMax"] < 21.875 * 2 ** (scene_detection_bits - 8)
            else:
                if not luma_scenecut_prev:
                    luma_scenecut = frame.props["LumaMin"] > 251.125 * 2 ** (scene_detection_bits - 8) or \
                                    frame.props["LumaMax"] < 3.875 * 2 ** (scene_detection_bits - 8)
                else:
                    luma_scenecut = frame.props["LumaMin"] > 249.125 * 2 ** (scene_detection_bits - 8) or \
                                    frame.props["LumaMax"] < 5.875 * 2 ** (scene_detection_bits - 8)

            if luma_scenecut and not luma_scenecut_prev:
                diffs[current_frame] = frame.props["LumaDiff"] + 2.0
            else:
                diffs[current_frame] = frame.props["LumaDiff"] + scene_detection_scenecut
                
            luma_scenecut_prev = luma_scenecut
        print(f"\033[KFrame {current_frame + 1} / Scene detection complete / {(current_frame + 1) / (time() - start):.02f} fps")

        great_diffs = diffs.copy()
        great_diffs[great_diffs < 1.0] = 0
        start_frames = scene_detection_split_scene(great_diffs, diffs, 0, len(diffs)) + [scene_detection_clip.num_frames]
        for i in range(len(start_frames) - 1):
            scenes["scenes"].append({"start_frame": int(start_frames[i]), "end_frame": int(start_frames[i + 1]), "zone_overrides": None})
        print(f"\033[KFrame [{scene_detection_rjust(start_frames[i])}:{scene_detection_rjust(start_frames[i + 1])}] / Scene creation complete")
    

# Metric
if zones_file:
    zones_f = zones_file.open("w")

for i, scene in enumerate(scenes["scenes"]):
    if zones_file:
        zones_f.write(f"{scene["start_frame"]} {scene["end_frame"]} svt-av1\n")

if zones_file:
    zones_f.close()

if scenes_file:
    with scenes_file.open("w") as scenes_f:
        json.dump(scenes, scenes_f)
