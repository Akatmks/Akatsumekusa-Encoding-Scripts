#!/usr/bin/env python3

# Progression Boost
# Copyright (c) Akatsumekusa and contributors
# Thanks to Ironclad and their grav1an, Miss Moonlight and their Lav1e,
# Trix and their autoboost, and BoatsMcGee and their Normal-Boost.


# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# The guide and config starts approximately 80 lines below this. Start
# reading from there.
#
# For the people that don't want too much tinkering and only want to     # <<<<  This pattern will guide you to only the necessary  <<<<<<<<<<<
# adjust the most basic options and get a good result fast (one that's   # <<<<  guide and settings.  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# better than av1an's `--target-quality`!), you would only need to       # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# change three options below. Go down, and only read paragraphs that     # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# have arrows on the right just like this very paragraph. There will be  # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# more guides below to lead you!                                         # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------


import argparse
from collections.abc import Callable
import copy
from datetime import datetime
from functools import partial
import json
import math
import numpy as np
from numpy.polynomial import Polynomial
from numpy.random import default_rng
import os
from pathlib import Path
import platform
from scipy import fftpack, signal
import shutil
import subprocess
from time import time
from typing import Optional
import traceback
import vapoursynth as vs
from vapoursynth import core

if platform.system() == "Windows":
    os.system("")

class NumpyEncoder(json.JSONEncoder):
    def default(self, object):
        if isinstance(object, np.generic):
            return object.item()
        if isinstance(object, np.ndarray):
            return object.tolist()
        else:
            return super(NumpyEncoder, self).default(object)

parser = argparse.ArgumentParser(prog="Progression Boost", epilog="For more configs, open `Progression-Boost.py` in a text editor and follow the guide at the very top")
parser.add_argument("-i", "--input", type=Path, required=True, help="Source video file")
parser.add_argument("--encode-input", type=Path, help="Source file for test encodes. Supports both video file and vpy file (Default: same as `--input`). This file is only used to perform probe encodes, while all other processes will be performed using the video file specified in `--input`. Note that if you apply filtering for test encodes, you probably also want to apply the same filtering before metric calculation, which can be set via `metric_reference` in the `Progression-Boost.py` file itself")
parser.add_argument("--encode-vspipe-args", nargs="+", help="VSPipe argument for test encodes.")
parser.add_argument("--input-scenes", type=Path, help="Perform your own scene detection and skip Progression Boost's scene detection")
parser.add_argument("-o", "--output-scenes", type=Path, required=True, help="Output scenes file for encoding")
parser.add_argument("--output-roi-maps", type=Path, help="Directory for output ROI maps, relative or absolute. The paths to ROI maps are written into output scenes")
group = parser.add_mutually_exclusive_group()
group.add_argument("--zones", type=Path, help="Zones file for Progression Boost. Check the guide inside `Progression-Boost.py` for more information")
group.add_argument("--zones-string", help="Zones string for Progression Boost. Same as `--zones` but fed from commandline")
parser.add_argument("--temp", type=Path, help="Temporary folder for Progression Boost (Default: output scenes file with file extension replaced by „.boost.tmp“)")
parser.add_argument("-r", "--resume", action="store_true", help="Resume from the temporary folder. By enabling this option, Progression Boost will reuse finished or unfinished testing encodes. This should be disabled should the parameters for test encode be changed")
parser.add_argument("-v", "--verbose", action="count", default=0, help="Report more details of Progression Boost. This parameter can be specified up to 2 times")
args = parser.parse_args()
input_file = args.input
probing_input_file = args.encode_input
if probing_input_file is None:
    probing_input_file = input_file
probing_input_vspipe_args = args.encode_vspipe_args
input_scenes_file = args.input_scenes
scenes_file = args.output_scenes
roi_maps_dir = args.output_roi_maps
zones_file = args.zones
zones_string = args.zones_string
temp_dir = args.temp
if not temp_dir:
    temp_dir = scenes_file
    if temp_dir.with_suffix("").suffix.lower() == ".scenes":
        temp_dir = temp_dir.with_suffix("")
    temp_dir = temp_dir.with_suffix(".boost.tmp")
scene_detection_temp_dir = temp_dir / "scene-detection"
progression_boost_temp_dir = temp_dir / "progression-boost"
character_boost_temp_dir = temp_dir / "characters-boost"
for dir_ in [scene_detection_temp_dir, progression_boost_temp_dir, character_boost_temp_dir]:
    dir_.mkdir(parents=True, exist_ok=True)
resume = args.resume
verbose = args.verbose


# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Before everything, the codes above are for commandline arguments.      # <<<<  This pattern will guide you to only the necessary  <<<<<<<<<<<
# The commandline arguments are only for specifying inputs and outputs   # <<<<  guide and settings.  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# while all encoding settings need to be modified within the script      # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# starting below.                                                        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# 
# To run the script, if you're using a preset with Character Boost, use  # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# ```sh
# python Progression-Boost.py --input INPUT.mkv --output-scenes OUTPUT.scenes.json --output-roi-maps OUTPUT.roi-maps
# ```
# If you're not using Character Boost, omit the last part and use        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# ```sh
# python Progression-Boost.py --input INPUT.mkv --output-scenes OUTPUT.scenes.json
# ```
# Read the help for all commandline arguments using                      # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# ```sh
# python Progression-Boost.py --help
# ```
#
# After you've run Progression Boost, run av1an for the final encode:    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# ```sh
# av1an -i INPUT.mkv -o OUTPUT.mkv --scenes OUTPUT.scenes.json --workers WORKERS
# ```
#
# On this note, if you don't like anything you see anywhere in this
# script, pull requests are always welcome.
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Have you noticed that we offers multiple presets for Progression       # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# Boost? The guide and explanations are exactly the same for each        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# presets. The difference is only the default value selected. Of course  # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# as you continue reading, you can always adjust the values for your
# needs.

# Here are the guide to the most necessary settings.                     # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#
# First, here are the settings for the encoder's encoding parameters.    # <<<<  This pattern will guide you to only the necessary  <<<<<<<<<<<
# If you've selected one of the 8 presets with regular metric based      # <<<<  guide and settings for presets with regular metric based  <<<<
# boosting, you need to adjust these 3 parameters:                       # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# * `metric_dynamic_preset`                                              # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# * `probing_dynamic_parameters`                                         # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# * `final_dynamic_parameters`                                           # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# If you've selected the preset with Character Boost only or the Scene   # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# Detection preset, you need to adjust these 3 parameters:               # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# * `metric_disabled_crf`                                                # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# * `metric_dynamic_preset`                                              # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# * `final_dynamic_parameters`                                           # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#
# If you've selected one of the 8 presets with regular metric based      # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# boosting, this is the only necessary parameter to adjust for metric:   # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# * `metric_target`                                                      # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#
# Search for these keywords inside the file and you'll be right          # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# there. The <<< pattern on the right will also lead you to there.       # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#
# If you've selected any of the 5 presets with Character Boost, you can
# of course leave Character Boost as is and it will do its job, but if
# you want to adjust, search for `Section: Character Boost`, and you'll
# be able to adjust there.
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Progression Boost has three separate modules, Scene Detection,
# Progression Boost, and Character Boost.
# 
# Scene Detection performs scene detection using various methods,
# including VapourSynth based methods and av1an based methods.
#
# Progression Boost performs two probe encodes to find the `--crf` that
# will hit the set metric target, ensuring the quality throughout the
# encode.
#
# Character Boost uses character recognition model to specifically
# boost characters on the screen using both ROI map and `--crf`.
# 
# These three modules are individually togglable.
# For example, you can skip Scene Detection by supplying your own scene
# detection generated from, let's say, an ML based scene detection
# scripts using `--input-scenes`. You can also skip Progression Boost
# step, relying on fixed `--crf` to maintain a baseline quality and
# then hyperboost characters using Character Boost. You can also skip
# both Progression Boost and Character Boost and this script now
# becomes a scene detection script.
# ---------------------------------------------------------------------
# There are five sections in the guide below. Search for
# "Section: Section Name" to jump to the respected sections.
# The five sections are:
#   Section: General
#   Section: Scene Detection
#   Section: Progression Boost
#   Section: Character Boost
#   Section: Zones
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------


class DefaultZone:
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Section: General
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# How should this script load your source video? Select the video
# provider for both this Python script and for av1an
    source_clip = core.lsmas.LWLibavSource(input_file.expanduser().resolve(), cachefile=temp_dir.joinpath("source.lwi").expanduser().resolve())
    source_provider = "lsmash"
# If you want to use BestSource instead, comment the lines above and
# uncomment the lines below.
    # source_clip = core.bs.VideoSource(input_file)
    # source_provider = "bestsource"

# This `source_clip` above is used in all three modules of Progression
# Boost. Let's say if your source has 5 seconds of intro LOGO, and you
# want to cut it away, this is what you need to do:
# First, for all the processes within Progression Boost, uncomment the
# lines below:
    # source_clip = source_clip[120:]
# And then, for av1an, you should create a VapourSynth file like this
# and feed it through Progression Boost's `--encode-input` commandline
# option:
# ```py
# from vapoursynth import core
#
# src = core.lsmas.LWLibavSource(YOUR_INPUT_FILE)[120:]
# src.set_output()
# ```

# Zoning information: `source_clip` and `source_provider` are not
# zoneable, but you can write VapourSynth code to `core.std.Splice` it
# yourself. Make sure you do the same for `--encode-input` and final
# encode as well.
# ---------------------------------------------------------------------
# We highly recommend using a SVT-AV1 derived encoder that supports
# quarterstep `--crf`, which includes all the major forks from
# SVT-AV1-PSY, such as svt-av1-psyex, 5fish/SVT-AV1-PSY, and
# SVT-AV1-HDR. However, if you don't have that luxury, and your encoder
# reported unrecognised `--crf`, you can disable this at the expense of
# precision.
    quarterstep_crf = True
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------


# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Section: Scene Detection
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# In the grand scheme of scene detection, av1an is the more universal
# option for scene detection. It works well in most conditions.
#
# Depending on the situations, you may want to use
# `--sc-method standard` or `--sc-method fast`.
#
# The reason `--sc-method fast` is sometimes preferred over
# `--sc-method standard` is that `--sc-method standard` will sometimes
# place scenecut not at the actual frame the scene changes, but at a
# frame optimised for encoder to reuse information.
# `--sc-method fast` is preferred because, first, the benefit from this
# optimisation is insignificant for most sources, and second, it means
# Progression Boost (or any other boosting scripts) will be much less
# accurate as a result, since scenes with such optimisation can contain
# frames from nearby scenes, which said frames will then certainly be
# overboosted or underboosted.
#
# However, in sections that's challenging for scene detection, such as
# a continuous cut many times the length of
# `scene_detection_extra_split` featuring lots of movements but no
# actual scenecuts, or sections with a lot of very fancy transition
# effects between cuts, `--sc-method standard` should be always
# preferred. The aforementioned additional optimisations are very
# helpful in complex sections and `--sc-method standard` greatly
# outperforms `--sc-method fast` in sources with such sections.
#
# You should use `--sc-method standard` if you anime contains sections
# challenging for scene detection such as what's mentioned above.
# Otherwise, `--sc-method fast` or WWXD or SCXVID based detection
# introduced below should always be preferred.
# 
# If you want to use av1an for scene detection, comment the line
# specifying `scene_detection_method = "vapoursynth"` in the next
# section and uncomment the line specifying av1an below.
    # scene_detection_method = "av1an".lower()
# Specify av1an parameters. You need to specify all parameters for an
# `--sc-only` pass other than `-i`, `--temp` and `--scenes`.
    def scene_detection_av1an_parameters(self) -> list[str]:
        return (f"--sc-method standard"
# Below are the parameters that should always be used. Regular users
# would not need to modify these.
              + f" --sc-only --extra-split {self.scene_detection_extra_split} --min-scene-len {self.scene_detection_min_scene_len} --chunk-method {self.source_provider}").split()

# av1an is mostly good, except for one single problem: av1an often
# prefers to place the keyframe at the start of a series of still,
# unmoving frames. This preference even takes priority over placing
# keyframes at actual scene changes. For most works, it's common to
# find cuts where the character will make some movements at the very
# start of a cut, before they settles and starts talking. Using av1an,
# these few frames will be allocated to the previous scenes. These are
# a low number of frames, with movements, and after an actual scene
# changes, but placed at the very end of previous scene, which is why
# they will often be encoded badly. They most likely would be picked up
# by Progression Boost to be given a big boost, but compared to av1an,
# WWXD or Scxvid is more reliable in this matter, and would have less
# potentials for issues like this.
#
# Similar to `--sc-method fast` against `--sc-method standard`, WWXD
# and Scxvid struggles in sections challenging for scene detection,
# such as a continuous cut many times the length of
# `scene_detection_extra_split` featuring lots of movements but no
# actual scenecuts, or sections with a lot of very fancy transition
# effects between cuts. WWXD or Scxvid tends to mark either too much or
# too few keyframes. Although this is largely alleviated by the
# additional scene detection logic in this script, you should prefer
# `--sc-method standard` if your source contains long sections of very
# challenging material unless you're boosting the worst frames to be
# good.
#
# In general, you should always use WWXD or Scxvid if you cares about
# the worst frames. For encodes targeting a good mean quality, if there
# are no sections difficult for scene detection, WWXD or Scxvid should
# always be preferred. If there are such sections, as explained above
# when introducing av1an-based scene detection, `--sc-method standard`
# should be preferred.
# 
# Progression Boost provides two options for VapourSynth-based scene
# detection, `wwxd` and `wwxd_scxvid`. `wwxd_scxvid` is slightly safer
# than `wwxd` alone, but multiple times slower. You should use
# `wwxd_scxvid` unless it's too slow, which `wwxd` can be then used. If
# you want to use VapourSynth-based scene detection, comment the
# `scene_detection_method` line above for av1an, and uncomment the line
# below for VapourSynth.
    scene_detection_method = "vapoursynth".lower()
# Select which VapourSynth based methods you're going to use for scene
# detection
    # scene_detection_vapoursynth_method = "wwxd_scxvid".lower() # Preferred
    scene_detection_vapoursynth_method = "wwxd".lower() # Fast
#
# For VapourSynth based scene detection to work, make sure you selected
# the correct colour range depending on your source, whether it is
# limited or full. For anime, it's almost always limited.
    scene_detection_vapoursynth_range = "limited".lower()
    # scene detection_vapoursynth_range = "full".lower()

# On this note, in case in some works the complex scenes are only in
# the OP and ED but not in the main episode, we've created a zone spec
# for this exact situation. Once you've read through the guide and
# understand how to use zones, you can set VapourSynth based scene
# detection here as default and then use the builtin_av1an zone for OP
# and ED.

# You can also provide your own scene detection via `--input-scenes`.
# You must uncomment the above two options and uncomment this option
# for it to work.
    # scene_detection_method = "external".lower()

# `--resume` information: If you've modified anything scene detection
# related, you need to delete everything in `scene-detection` folder in
# the temporary directory except for the four .txt files starting with
# `luma-`, and then you can rerun the script.

# Zoning information: all three `scene_detection_method` is zoneable,
# which means you can mix av1an based scene detection with VapourSynth
# based scene detection, as well as external scene detection fed from
# `--input-scenes`. However, `scene_detection_av1an_parameters` is not
# zoneable. There would only be one av1an scene detection pass.
# ---------------------------------------------------------------------
# Specify the desired scene length for scene detection. The result from
# this scene detection will be used both for test encodes and the final
# encodes.
    scene_detection_extra_split = 264
    scene_detection_min_scene_len = 12
# The next setting is only used if VapourSynth based scene detection
# method is selected.
#
# WWXD has the tendency to flag too much scenechanges in complex
# everchanging sections. This setting marks the length of a scene for
# the scene detection mechanism to stop dividing it any further.
# However, this does not mean there won't be scenes shorter than this
# setting. It's likely that scenes longer than the this setting will be
# divided into scenes that are shorter than this setting. The hard limit
# is still specified by `scene_detection_min_scene_len`.
# Also, this setting only affects sections where there are a lot of
# scenechanges detected by WWXD. For calmer sections where WWXD doesn't
# flag any scenechanges, the scene detection mechanism will only
# attempt to divide a scene if it is longer than
# `scene_detection_extra_split`, and this setting has no effects.
#
# If you are using Character Boost, you should set this number lower to
# maybe 33. If you are not going to enable Character Boost, the default
# 60 would be fine.
    scene_detection_target_split = 49

# `--resume` information: If you've modified anything scene detection
# related, you need to delete everything in `scene-detection` folder in
# the temporary directory except for the four .txt files starting with
# `luma-`, and then you can rerun the script.

# Zoning information: `scene_detection_extra_split` and
# `scene_detection_min_scene_len` are only zoneable if you use
# VapourSynth based scene detection.
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------


# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Section: Progression Boost
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Progression Boost is the main module of this script. We perform two
# probe encodes, measure the metric result of these probe encodes, and
# then deduct a final `--crf` for the final encode.

# Enable Progression Boost module by setting the following value to
# True:
    metric_enable = True
# Even if you disable Progression Boost, you cannot skip this whole
# section, as you need to set your final encoding parameters here. Read
# first 3 cells below to find the settings you'll need to change.

# `--resume` information: Toggling modules is completely resumable.
# Just rerun the script and it will work... unless you've changed
# individual settings for each module, then you need to check the
# `--resume` information for each settings.
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Set the encoding parameters!
# For the parameters below, you will see two sets of variables for you
# to adjust, one of them is for the probing passes, and one of them
# will be set into your output scenes file and for the final encoding
# pass.
#
# Play special attention that a lot of settings below not only apply to
# this Progression Boost module, but also the next Character Boost
# module. They should be listed separately in the Character Boost
# module, but that would make it very difficult to adjust because
# you'll have to scroll up and down all the time. Any variables with
# prefix `probing_` is for the probing passes, any variables with
# `metric_` applies to this Progression Boost module, and any variables
# with prefix `final_` applies after both Progression Boost and
# Character Boost module finishes.

# First, `--crf`:

# Presuming that you're enabling this Progression Boost module, let's
# set the maximum and minimum clamp for the `--crf` value for the final
# encode.
# 
# Although this `--crf` clamp is for your final encoding pass, and not
# the two probes, it only applies to this very module. Later in the
# Character Boost module, you may boost `--crf` further, and that
# boosting is not covered by this clamp set here. For that, you need to
# go down to the Character Boost module and set it there.
# 
# To set this clamp, first, there is a minimum and maximum from the
# nature of this boosting method.
# Let's talk about maximum `--crf` value. First, you might be surprised
# that `--crf` values can go so high as to 50.00 while still delivering
# a decent quality. This is because of the internal TPL system to boost
# the quality of a block if it is shared by other frames in the scene.
# Especially for still scenes, this TPL system can take care of
# everything and deliver a good quality.
# However, there's a catch, if this scene were not completely still, and
# there were two or three frames that are actually different, since it's
# only 2 or 3 frames, the internal the TPL system will not boost these
# frames as hard, it will result these two frames being encoded poorly.
# Progression Boost has a clever frame selection system in place to
# prevent this. However, to perfectly protect these frames, you need the
# system to select enough frames to measure, and that means more time
# calculating metric. To not spend more time, you might just well
# sacrifices a tiny little bit and use a safer maximum `--crf`. It's
# really a tiny little bit because a `--crf 50.00` encode is barely
# bigger than `--crf 60.00` encode.
# If you've adjusted the script to select more frames than the default
# of your downloaded Progression Boost Preset, you can try
# `--crf 60.00` here, but `--crf 50.00` should also be fine.
    metric_max_crf = 50.00
# For the minimum `--crf` value, the precision of this boosting method
# deteriorates at very low `--crf` values. And also unless you're
# willing to spend 10% of your entire episode in a single 6 second
# scene, you really don't want it that low.
# That's said, if you are aiming for the highest quality, fell free to
# lower this further to `--crf 6.00`.
    metric_min_crf = 8.00
# Our first probe will be happening at `--crf 24.00`. If the quality of
# the scene is worse than `metric_target`, we will perform our second
# probe at a better `--crf`. In very rare and strange scenarios, this
# second probe performed at better `--crf` could receive an even worse
# score than the first probe performed at worse `--crf`. It could be
# due to some weirdness in the encoder or the metric. In this case
# we want to have a fallback `--crf` to use. Set this fallback `--crf`
# here.
    def metric_unreliable_crf_fallback(self):
        return self.metric_min_crf + 3.00

# Above are the clamp from the nature of this boosting method, but
# there are also additional factors to consider depending on your
# scenario.
# For maximum `--crf` value, for example, if you're using very high
# `--psy-rd` such as `--psy-rd 4.00`. It's likely that it may produce
# too much unwanted artefacts at high `--crf` values. For this reason,
# you can limit the `metric_max_crf`. To limit the `--crf` value,
# uncomment the code above for setting `metric_max_crf`, and uncomment
# the line below to set a new one.
    # metric_max_crf = 32.00

# In addition to setting our maximum and minimum clamp, we can also
# adjust our `--crf` values dynamically.
    def metric_dynamic_crf(self, crf: float) -> float:
# For example, one common usage is for encodes targeting lower filesize
# targets to dampen the boost. We willingly allow some scenes to have a
# worse quality than the target we set, in order to save space for all
# the other scenes.
# To enable dampening for lower filesize targets, uncomment the two
# lines below.
        # if crf < 26.00:
        #     crf = (crf / 26.00) ** 0.60 * 26.00
# You can also write your own methods here. This function takes in
# `--crf` of any precision, and return a `--crf` of any precision.
# Note that the clamp of `metric_max_crf` and `metric_min_crf` happens
# before this function and there are no clamps after this function.
        return crf

# At last, if you've disabled this Progression Boost module, and you     # <<<<  Adjust this if you're using the Character Boost only or  <<<<<
# only want Character Boost, set a base `--crf` here. This value has no  # <<<<  Scene Detection preset that skips metric based boosting.  <<<<
# effect if Progression Boost module is enabled.                         # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#
# This `--crf` value will also be clamped by `metric_min_crf` and
# `metric_max_crf`.                                                      # <<<< ↓ Adjust it here. <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    metric_disabled_crf = 28.00

# Although we already clamp once for Progression Boost module above,
# the Character Boost module might also boost the `--crf` value. Let's
# clamp this one last time.
# This clamp is applied after both Progression Boost and Character
# Boost has finished.
    final_min_crf = 6.50

# `--resume` information: If you changed parameters for probing, you
# need to delete everything in `progression-boost` folder inside the
# temporary directory, and then you can rerun the script.
# If you changed `metric_` or `final_` parameters for the output, you
# don't need to delete anything in temporary directory, and the changes
# will be updated once you rerun the script.
# ---------------------------------------------------------------------
# Second, `--preset`:

# Progression Boost features a magic number based preset readjustment
# system, and we can reasonably simulate what will be happening at
# slower final encode based on our very fast probe encodes.
# 
# For this reason, we recommend setting very fast `probing_preset`.
# For example, if on a certain system:
#   encoding at `--preset 9` takes 3 minutes,
#   encoding at `--preset 8` takes 3 minutes,
#   encoding at `--preset 7` takes 4 minutes,
#   encoding at `--preset 6` takes 7 minutes.
# In this example, we will recommend `--preset 7` for normal boosting,
# and `--preset 6` if you are targeting the very high quality targets
# and want to minimise error.
# If you have a faster system than above where it has a the point where
# the overheads take more time than the actual encoding, you can select
# a slower `--preset`.
# However, don't use slower `--preset` thinking it may be safer, the
# default `--preset 7` is safe enough. Boosting  should never take more
# than one third of the entire encoding time. If you have more time,
# you should use a slower `--preset` for final encoding pass and don't
# waste time on boosting.
    probing_preset = 7

# We'll now set the `--preset` for the output scenes file for our        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# eventual final encode. Put your `--preset` after the `return` below,   # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# and you'll be good to go.                                              # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#
# Some of us may prefer using a mix of different `--preset`s, either
# because some of our parameters will be safer at slower `--preset`
# when the scene has very high (bad) `--crf`, or because one `--preset`
# is too fast for our target encoding time, and the next `--preset` is
# too slow.
# To support dynamic `--preset`, this is a function that receives a
# `--crf`, and should return a `--preset` for final encode.
#
# Note that this function happens at the very early stage of
# Progression Boost module. The `--crf` it receives is straight from
# the linear model and has only be clamped by `metric_max_crf` and
# `metric_min_crf`. The `--crf` this function receives here will be
# very different from the eventual output. You can use `--resume` and
# `--verbose` to test out the right threshold for your dynamic
# `--preset`.                                                            # <<<< ↓ Adjust it here. <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    def metric_dynamic_preset(self, crf: float) -> int:
        return 2

# `--resume` information: If you changed parameters for probing, you
# need to delete everything in `progression-boost` folder inside the
# temporary directory, and then you can rerun the script.
# If you changed `metric_` parameters for the output, you don't need to
# delete anything in temporary directory, and the changes will be
# updated once you rerun the script.
# ---------------------------------------------------------------------
# Third, every other parameters:

# We've set `--crf` and `--preset`, and now we're setting all the        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# remaining parameters.                                                  # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# 
# For `final_dynamic_parameters`, use every parameters you plan to use   # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# for your eventual final encode, but:                                   # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#   Do not set `--crf` and `--preset` for `final_dynamic_parameters`,    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#   because we've already set it above.                                  # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#   Do not set `-i` and `-b` and use the same parameters as you would    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#   feed into av1an `--video-params`.                                    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# For `probing_dynamic_parameters`, use the same parameters you as       # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# `final_dynamic_parameters`, but:                                       # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#   Do not set `--crf` and `--preset` for `probing_dynamic_parameters`,  # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#   because we've already set it above.                                  # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#   Do not set `-i` and `-b` and use the same parameters as you would    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#   feed into av1an `--video-params`.                                    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#   Set `--film-grain 0` for `probing_dynamic_parameters` if it is       # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#   nonzero in `final_dynamic_parameters`. `--film-grain` is a           # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#   generative process and we will get metric results that doesn't       # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#   match our visual experience.                                         # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#
# If you want to set a set of fixed parameters, fill it in directly      # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# after the `return` token.                                              # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# These two functions also support using dynamic parameters for both
# testing and final encodes. A common usage of using dynamic parameters
# is when we're using very high `--psy-rd` values such as
# `--psy-rd 4.0`. At high `--crf` values, such high `--psy-rd` is
# likely to produce too much encoding artefacts. For this reason, we
# can dynamically lower this when the `--crf` is very high.
# If you want to use dynamic parameters, these two functions receives
# a `--crf` and should return a list of string containing all the
# parameters except `--crf` and `--preset`.
# Note that for `final_dynamic_parameters`, it is performed at the very
# last stage of this boosting script, hence the `final_` prefix instead
# of `metric_` prefix, which means the `--crf` this function receives
# not only includes `--crf` result from this Progression Boost module
# after `metric_dynamic_crf`, but also the `--crf` boosts in the next
# Character Boost module as well.                                        # <<<< ↓ Adjust it here. <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    def probing_dynamic_parameters(self, crf: float) -> list[str]:
        return """--lp 3 --keyint -1 --input-depth 10 --scm 0
                  --tune 3 --luminance-qp-bias 12 --qm-min 8 --chroma-qm-min 10
                  --complex-hvs 0 --psy-rd 1.0 --spy-rd 0
                  --color-primaries 1 --transfer-characteristics 1 --matrix-coefficients 1 --color-range 0""".split()
    def final_dynamic_parameters(self, crf: float) -> list[str]:
        return """--lp 3 --keyint -1 --input-depth 10 --scm 0
                  --tune 3 --luminance-qp-bias 12 --qm-min 8 --chroma-qm-min 10
                  --complex-hvs 1 --psy-rd 1.0 --spy-rd 0
                  --color-primaries 1 --transfer-characteristics 1 --matrix-coefficients 1 --color-range 0""".split()

# `--resume` information: If you changed parameters for probing, you
# need to delete everything in `progression-boost` folder inside the
# temporary directory, and then you can rerun the script.
# If you changed `final_` parameters for the final output, you don't
# need to delete anything in temporary directory, and the changes will
# be updated once you rerun the script.
# ---------------------------------------------------------------------
# At last, av1an parameters:

# These are the av1an parameters for probe encodes.
# The only thing you would need to adjust here is `--workers`. The
# fastest `--lp` `--workers` combination is listed below:
#   32 threads: --lp 3 --workers 8
#   24 threads: --lp 3 --workers 6
#   16 threads: --lp 3 --workers 4
#   12 threads: --lp 3 --workers 3
    def probing_av1an_parameters(self, message: str) -> list[str]:
        return (f"--workers 8 --pix-format yuv420p10le"
# Below are the parameters that should always be used. Regular users
# would not need to modify these.
              + f" --chunk-method {self.source_provider} --encoder svt-av1 --audio-params -an --concat mkvmerge --force --video-params").split() + \
                [message]

# These are the photon noise parameters for your final encode. These
# are not applied in probe encodes.
#
# For `photon_noise`, we made it a function that you can dynamically
# adjust based on the luminance of the frame. The three parameters
# `luma_average`, `luma_min`, `luma_max` are straight from
# `core.std.PlaneStats` of the luma plane of `source_clip`. The shape
# of the three ndarrays are `(num_frames_in_the_scene,)`.
# Note that the default value for `photon_noise` in scenes file is
# `None` instead of `0`, and the result for `photon_noise` `0` is
# undefined.
    def final_dynamic_photon_noise(self, luma_average: np.ndarray[np.float32], luma_min: np.ndarray[np.float32], luma_max: np.ndarray[np.float32]) -> Optional[int]:
        return None
    final_photon_noise_height = None
    final_photon_noise_width = None
    final_chroma_noise = False

# `--resume` information: If you changed parameters for probing, you
# need to delete everything in `progression-boost` folder inside the
# temporary directory, and then you can rerun the script.
# If you changed `final_` parameters for the final output, you don't
# need to delete anything in temporary directory, and the changes will
# be updated once you rerun the script.

# Zoning information: `probing_av1an_parameters` is not zoneable.
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Once the test encodes finish, Progression Boost will start
# calculating metric for each scenes.

# When calculating metric, we don't need to calculate it for every
# single frame. It's very common for anime to have 1 frame of animation
# every 2 to 3 frames. It's not only meaningless trying to calculate
# repeating frames, it's actually very dangerous because it will dilute
# the data and make the few bad frames less arithmetically significant.
#
# First, we have three methods to selectively pick the frames that are
# most likely to be bad out. This is to make sure that we don't
# actually miss these frames.
# Since we're disproportionately picks the bad frames, the eventual mean
# or percentile we will calculate is no longer the real mean or
# percentile across the video, but just the mean or percentile of the
# frames we've picked. How aggressive we pick these frames also affects
# how aggressive the eventual boost would be.
# If you're using a mean-based method to summarise the data later, keep
# the number of frames picked here at a modest amount, such as one
# third of the total amount of frames picked. If you're using a
# percentile-based method to boost the worst frames, you can consider
# picking half of the frames you're measuring here.
# However, under no circumstance should you not pick any frames from at
# least one of these methods.
#
# The first idea to pick the likely bad frame is to measure how much
# difference there are between the frame and the frame before it.
# In the first method, we transform the diff through various methods,
# and then we pick the local maxima of the transformed result. This
# method is robust against most situation, including fades and big
# character movements.
    metric_peak_transformed_diff_frames = 4
# In the second method, we select frames based on the raw diff. This is
# more sensitive to small movements that would potentially cause
# problems.
    metric_highest_diff_frames = 3

# The third method to pick the likely bad frame is to calculate the
# raw pixel by pixel difference between the source and the first probe
# encode. This is the most rudimentary of metric, but it works
# surprisingly well, even better than PSNR and XPSNR alike. However,
# this method is extremely slow due to that it has to decode every
# frame in the scene. We only recommend using this method in the
# slowest and highest quality situations. For other cases, if you want
# to be safer, you should measure more frames in such as
# `metric_highest_diff_frames`.
    metric_highest_probing_diff_frames = 0
#
# After that, we now use a randomiser to select frames across the whole
# scene. It's common for anime to have 1 new frame followed by 2 to 4
# repeating frame that are exactly the same as the frame before.
# To adapt to this frakn arrangement, we separate the frames into two
# brackets at 2 times MAD but based on the 40th percentile instead of
# median value. The lower bracket are most likely be repeating frames,
# and the upper bracket are most likely to be frames we want to
# measure.
# A good starting point for a mean-based method is to measure 6 and 3
# frames respectively from each bracket. If you have the computing
# power and you want to be relatively safe, use maybe 10 and 5. If you
# want to speed up metric calculation, you can try 4 and 2 for these
# while also reducing `metric_highest_diff_frames` to 2.
    metric_upper_diff_bracket_frames = 4
    metric_lower_diff_bracket_frames = 2
# We select frames from the two brackets randomly, but we want to avoid
# picking frames too close to each other, because, in anime content,
# these two frames are most likely exactly the same.
    metric_diff_brackets_min_separation = 3
# If there are not enough frames in the upper bracket to select, we
# will select some more frames in the lower diff bracket. If the number
# of frames selected in the upper diff bracket is smaller than this
# number, we will select additional frames in the lower bracket until
# this number is reached.
    metric_upper_diff_bracket_fallback_frames = 2
#
# All these diff sorting and selection excludes the first frame of the
# scene since the diff data of the first frame is compared against the
# last frame from the previous scene and is irrelevant. In addition,
# the first frame as the keyframe often has great quality... until it
# doesn't. It's safer to select the first frame as well. Do you want
# to always include the first frame in metric calculation?
    metric_first_frame = 1
#
# Sometimes, sometimes SVT-AV1-PSY will encode the last frame of a
# scene slightly worse than the rest of the frames. Do you want to
# always include the first frame in metric calculation?
    metric_last_frame = 1

# `--resume` information: If you changed the frame selection, you need
# to delete everything in `progression-boost` folder inside the
# temporary directory, including the probe encodes, and then you can
# rerun the script.
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Progression Boost currently supports two methods calculating metrics,
# FFVship and VapourSynth.
# FFVship is a standalone external program, while VapourSynth method
# supports vship and vszip.

# If you want to use VapourSynth based methods for calculating metrics,
# comment the line three paragraphs below for FFVship and uncomment the
# line below for VapourSynth.
    metric_method = "vapoursynth".lower()
#
# For VapourSynth based metric calculation, if you've applied filtering
# via `--encode-input`, make sure you match it and apply the same
# filtering here:
    metric_reference = source_clip.resize.Bicubic(filter_param_a=0.0, filter_param_b=0.0, format=vs.YUV420P10)
#
# For VapourSynth based metric calculation, this function allows you to
# perform some additional filtering before calculating metrics.
    def metric_process(self, clip: vs.VideoNode) -> vs.VideoNode:
# First, here is a hack if you want higher speed calculating metrics.
# What about cropping the clip from 1080p to 900p or 720p? This is
# tested to have been working very well, producing very similar final
# `--crf`swhile increasing measuring speed significantly. However,
# since we are cropping away outer edges of the screen, for most anime,
# we will have proportionally more characters than backgrounds in the
# cropped compare. This may not may not be preferrable. If you want to
# enable cropping, uncomment the lines below to crop the clip to 900p
# before comparing.
        # clip = clip.std.Crop(left=160, right=160, top=90, bottom=90)
# If you want some other processing before calculating metrics, you can
# implement it here.
        return clip
        
# FFVship is only available if you've not applied filtering via
# `--encode-input`, and you don't plan to apply additional filtering
# before calculating metric. As of right now with FFVship version 3.0.2
# prerelease, FFVship is slower than vship, so vship is selected as the
# default for all presets.
# If you want to use FFVship, enable it by commenting the line above
# for VapourSynth and uncommenting the line below.
    # metric_method = "ffvship".lower()
# Specify extra FFVship parameters. You can specify `--threads`,
# `--gpu-threads`, `--gpu-id` or other operation related options. You
# must not specify any source or encoded related options, any frame
# selection related options, or any metric related options. Metric
# related options will be available in the next section of the guide.
    metric_ffvship_extra_parameters = []
#
# To avoid accidentally selecting the FFVship option when providing
# additional filtering, Progression Boost will refuse to run when
# `--encode-input` is provided. However, you can force it to continue
# by settings this to True:
    metric_continue_filtered_with_ffvship = False
# ---------------------------------------------------------------------
# What metric do you want to use?

# To use Butteraugli 3Norm via FFVship or vship, uncomment the lines
# below.
    # metric_better = np.less
    # metric_vapoursynth_calculate = core.vship.BUTTERAUGLI
    # metric_vapoursynth_metric = lambda self, frame: frame.props["_BUTTERAUGLI_3Norm"]
    # metric_ffvship_calculate = "Butteraugli"
    # metric_ffvship_intensity_target = None
    # metric_ffvship_metric = lambda self, frame: frame[1]

# Butteraugli 3Norm takes the average score over the whole frame, and
# it will not reflect if only a tiny fraction of the frame is bad. This
# is especially damaging in scenes where the majority of the background
# is still and has good quality, and only the character is moving and
# is encoded badly. 3Norm alone won't be able to reflect how bad the
# character is, which is where INFNorm comes in. INFNorm on its own is
# very, very sensitive, and we would not recommend using INFNorm
# directly even aiming for the highest quality targets. Instead we
# offers the following two options.
# The first one only mixes in INFNorm score if INFNorm score is more
# than 10 times the 3Norm score. This is more suitable for regular
# medium quality boosting.
    metric_better = np.less
    metric_vapoursynth_calculate = core.vship.BUTTERAUGLI
    def metric_vapoursynth_metric(self, frame):
        adjustment = frame.props["_BUTTERAUGLI_INFNorm"] * 0.027 - frame.props["_BUTTERAUGLI_3Norm"] * 0.27
        if adjustment < 0:
            adjustment = 0
        return frame.props["_BUTTERAUGLI_3Norm"] + adjustment
    metric_ffvship_calculate = "Butteraugli"
    metric_ffvship_intensity_target = None
    def metric_ffvship_metric(self, frame):
        adjustment = frame[2] * 0.027 - frame[1] * 0.27
        if adjustment < 0:
            adjustment = 0
        return frame[1] + adjustment

# The second option always mixes in 2.6% INFNorm on top of 3Norm score
# and is suitable for the highest quality boosting targets.
    # metric_better = np.less
    # metric_vapoursynth_calculate = core.vship.BUTTERAUGLI
    # metric_vapoursynth_metric = lambda self, frame: frame.props["_BUTTERAUGLI_3Norm"] + frame.props["_BUTTERAUGLI_INFNorm"] * 0.027
    # metric_ffvship_calculate = "Butteraugli"
    # metric_ffvship_intensity_target = None
    # metric_ffvship_metric = lambda self, frame: frame[1] + frame[2] * 0.027

# Same as the issue above with Butteraugli 3Norm, SSIMU2 are also not
# very sensitive to fine details, but it is faster, and is good enough
# for medium and low quality encodes. To use SSIMU2 via FFVship or
# vship, uncomment the lines below.
    # metric_better = np.greater
    # metric_vapoursynth_calculate = core.vship.SSIMULACRA2
    # metric_vapoursynth_metric = lambda self, frame: frame.props["_SSIMULACRA2"]
    # metric_ffvship_calculate = "SSIMULACRA2"
    # metric_ffvship_metric = lambda self, frame: frame[0]

# To use SSIMU2 via vszip, uncomment the lines below.
    # metric_better = np.greater
    # metric_vapoursynth_calculate = core.vszip.SSIMULACRA2
    # metric_vapoursynth_metric = lambda self, frame: frame.props["SSIMULACRA2"]

# `--resume` information: If you changed to a different metric or
# metric measurement, you need to delete `probe-encode-first.mkv` in
# `progression-boost` folder inside the temporary directory. By doing
# this, you won't reencode the first probe encode, but you will
# reencode the second probe encode due to internal machanics of
# Progression Boost. After deleting `probe-encode-first.mkv`, you can
# rerun the script.
# ---------------------------------------------------------------------
# After calcuating metric for frames, we summarise the quality for each
# scene into a single value. There are two main ways for this in new
# version of Progression Boost.

# The first is to directly observe the min or the max score of frames
# in the scene. This method is very aggressive, aiming at completely
# eliminate bad frames. It's suitable for the highest quality targets
# but may be too aggressive for medium or lower quality encodes.
#
# If you want to get the best quality, you should also increase the
# number of frames measured in order to prevent bad frames from
# slipping through.
    # def metric_summarise(self, scores: np.ndarray[np.float32]) -> np.float32:
    #     return np.min(scores)
    # def metric_summarise(self, scores: np.ndarray[np.float32]) -> np.float32:
    #     return np.max(scores)

# The second method is more gentle and more suitable for general use.
# The based of the second method is a mean based observation. And then
# we will observe the min or max score of frames in the scene. If the
# min or max score is tame and not specifically problematic, the mean
# based observation is not modified. If the min or max score is
# significant, we will offset the mean based observation to reflect on
# this.
# This method is aimed to achieve consistency in quality, aka, smallest
# standard deviation, while also addressing the bad frames in a less
# aggressive mannar than the first method. This method is suitable for
# the entire quality range from high quality to lower quality.
#
# Specifically to calculate mean, we use harmonic mean to calculate
# SSIMU2 score. This is studied by Miss Moonlight to have good
# representation of realworld viewing experience.
# There is a very rare edge case for harmonic mean, that when the score
# for a single frame dropped too low, it can skew the whole mean value
# to the point that scores for all other frames have essentially no
# effects on the final score. For this reason, we cap the SSIMU2 score
# to 15 before calculating harmonic mean.
# For Butteraugli score, we use root mean cube. This is suggested by
# Miss Moonlight and tested to have good overall boosting result.
#
# For SSIMU2 score, uncomment the lines below.
    # def metric_summarise(self, scores: np.ndarray[np.float32]) -> np.float32:
    #     if np.any((small := scores < 15)):
    #         scores = scores.copy()
    #         scores[small] = 15
    #         if verbose >= 1:
    #             print(f"\r\033[K{scene_frame_print(scene_n)} / Metric summarisation / Frames in this scene receive a metric score below 15 for test encodes.", end="\n")
    #
    #     mean = scores.shape[0] / np.sum(1 / scores)
    #     mean_0 = mean
    #
    #     median = np.median(scores)
    #     mad = np.median(np.abs(scores - median))
    #
    #     threshold = median + mad * 2.5
    #     scores = scores[scores <= threshold]
    #
    #     mean = scores.shape[0] / np.sum(1 / scores)
    #     mean_1 = mean
    #
    #     mad = np.median(np.abs(scores - median))
    #
    #     limit = median - mad * 3.0
    #     overlimit = np.min(scores) - limit
    #     for score_i in range(scores.shape[0] - 5 + 1):
    #         i_limit = np.median(scores[score_i:score_i + 5]) - mad * 3.0
    #         i_overlimit = np.min(scores[score_i:score_i + 5]) - i_limit
    #         overlimit = np.min([overlimit, i_overlimit])
    #     if overlimit > 0:
    #         overlimit = 0
    #
    #     mean += overlimit
    #     mean_2 = mean
    #
    #     if verbose >= 2:
    #         if mean_1 != mean_0 or mean_2 != mean_0:
    #             print(f"\r\033[K{scene_frame_print(scene_n)} / Metric summarisation / mean_0 {mean_0:.3f} / mean_1 {mean_1:.3f} / mean_2 {mean_2:.3f}", end="\n")
    #
    #     return mean
# For Butteraugli 3Norm score, uncomment the lines below.
    def metric_summarise(self, scores: np.ndarray[np.float32]) -> np.float32:
        mean = np.mean(scores ** 3) ** (1 / 3)
        mean_0 = mean

        median = np.median(scores)
        mad = np.median(np.abs(scores - median))

        threshold = median - mad * 2.5
        scores = scores[scores >= threshold]

        mean = np.mean(scores ** 3) ** (1 / 3)
        mean_1 = mean

        mad = np.median(np.abs(scores - median))

        limit = median + mad * 3.0
        overlimit = np.max(scores) - limit
        for score_i in range(scores.shape[0] - 5 + 1):
            i_limit = np.median(scores[score_i:score_i + 5]) + mad * 3.0
            i_overlimit = np.max(scores[score_i:score_i + 5]) - i_limit
            overlimit = np.max([overlimit, i_overlimit])
        if overlimit < 0:
            overlimit = 0

        mean += overlimit
        mean_2 = mean

        if verbose >= 2:
            if mean_1 != mean_0 or mean_2 != mean_0:
                print(f"\r\033[K{scene_frame_print(scene_n)} / Metric summarisation / mean_0 {mean_0:.3f} / mean_1 {mean_1:.3f} / mean_2 {mean_2:.3f}", end="\n")

        return mean

# If you want to use a different method than above to summarise the
# data, implement your own method here.
# 
# This function is called independently for every scene for every test
# encode.
    # def metric_summarise(self, scores: np.ndarray[np.float32]) -> np.float32:
    #     pass

# `--resume` information: If you changed `metric_summarise`, you need
# to delete `probe-encode-first.mkv` in `progression-boost` folder
# inside the temporary directory. By doing this, you won't reencode the
# first probe encode, but you will reencode the second probe encode due
# to internal machanics of Progression Boost. After deleting
# `probe-encode-first.mkv`, you can rerun the script.
# ---------------------------------------------------------------------
# After calculating the percentile, or harmonic mean, or other           # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# quantizer of the data, we fit the quantizers to a polynomial model     # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# and try to predict the lowest `--crf` that can reach the target        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# quality we're aiming at.                                               # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# Specify the target quality using the variable below.                   # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#
# Note that Progression Boost can only create the model based on test    # <<<<  These parameters are all you need to get a result you <<<<<<<<
# encodes performed at `--preset 7` by default. You will get much        # <<<<  want fast, but you are recommended to have a look at  <<<<<<<<
# better result in your final encode using a slower `--preset`. You      # <<<<  all the other settings once you become familiar with the <<<<<
# should account for this difference when setting the number below.      # <<<<  script. There's still a lot of improvements, timewise or  <<<<
# Maybe set it a little bit lower than your actual target.               # <<<<  qualitywise, you can have with all the other options.  <<<<<<<
    metric_target = 0.950

# `--resume` information: If you changed `metric_target`, just rerun
# the script and it will work. Unlike some other options, you don't
# need to delete anything in the temp folder for this change to update.
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------


# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Section: Character Boost
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Character boosting is a separate boosting system based on ROI (Region
# Of Interest) map as well as `--crf`. This utilises image segmentation
# model to recognise the character in the scene, and selectively boost
# the characters.
#
# Character Boost is immensely helpful in all anime and in all quality
# targets.
# In high quality encodes, a medium to aggressive Character Boost is
# the only method that's able to save weak artlines, provided that
# you've also set the best encoding parameters (`--max-32-tx-size 1
# --qp-scale-compress-strength [somewhere around 3]
# --tune [test the best option for your source]
# --psy-rd [test the best value for your source, normally 3.5 ~ 4]`).
# In lower quality targets, Character Boost can make sure you put your
# limited bitrate into parts that actually matters - the characters,
# and not the the background. Since flat character is actually easier
# to encode than background with textures, you can achieve
# significantly better watching experience with Character Boost.
#
# Enable character boosting by setting the line below to True.
    character_enable = True

# `--resume` information: Toggling modules is completely resumable.
# Just rerun the script and it will work... unless you've changed
# individual settings for each module, then you need to check the
# `--resume` information for each settings.
# ---------------------------------------------------------------------
# Set how aggressive character boosting should be.

# There are three different boosting methods for Character Boost. The
# first is ROI map based boosting. `--roi-map-file` is a parameter of
# SVT-AV1 derived encoders, that allows us to set quality level per
# Super Block.
# 
# Set how aggressive ROI map based boosting should be below.
# This value is the same scale as `--crf`, in the sense that the
# default `5.00` means the biggest character boost is 5.00 `--crf`
# better than background.
# The maximum recommended value for this is 7.00 ~ 8.00. If you want
# more aggressive character boosting beyond 7.00, applying them via the
# third value for `--crf` based boosting should be more effective.
#
# The maximum boost of the number specified below is only applied to
# the first frame of a scene. Later frames will be boosted less
# depending on how the hierarchial structure is commonly constructed.
#
# The number here should be positive.
    character_max_roi_boost = 5.50

# This second is a `--crf` based character boosting based on how much
# character occupies the screen.
# 
# For the encoder internally, boosting the whole scene is more
# efficient than ROI map based boosting. However this also boosts the
# background in addition to characters, so it may not be as effective.
# There are no minimum recommended value for this, but setting it at a
# low value such as 2.00 or 3.00 never hurts.
# There are no maximum value for this either. Once you've set the first
# ROI map based boosting to its maximum recommended value of 7.00 or
# above, you can put all your remaining boosting here as much as you
# want. For example, something like a very aggressive 20.00 will work
# just fine.
#
# In some works when there are annoying sections that eats too much
# bitrate, you can even disable Progression Boost module, relying on
# the base `--crf` set by `metric_unboosted_crf` to maintain a baseline
# consistency, and then hyperboost character here.
#
# The number here should be positive.
    character_max_crf_boost = 3.00

# The third is also a `--crf` based boosting method, but based on how
# much the character moves across the scene. This is to address the
# issue that weak lines often gets pretty poorly preserved when the
# character is moving.
# This detection is based on the character recognition model, and is
# not very accurate. There will be cases of false positive. For this
# reason, this method should only be treated as an addition to the
# first two methods. The recommended starting value for this is 4.50,
# and the maximum recommended value for this would be 8.00 ~ 10.00.
#
# The number here should be positive.
    character_max_motion_crf_boost = 4.00

# `--resume` information: If you changed any character boosting related
# settings, just rerun the script and it will work. Unlike some other
# options, you don't need to delete anything in the temp folder for the
# changes to update.
# ---------------------------------------------------------------------
# Select vs-mlrt backend for image segmentation model here. You should
# always use `fp16=True`. The resolution required for Character Boost
# is low and accuracies of one or two pixels doesn't matter at the
# slightest.
    def character_get_backend(self):
        import vsmlrt
        return vsmlrt.Backend.TRT(fp16=True)
# Zoning information: `character_get_backend` is not zoneable.
# ---------------------------------------------------------------------
    def character_get_model(self):
        import vsmlrt
        model = Path(vsmlrt.models_path) / "anime-segmentation" / "isnet_is.onnx"
        if not model.exists():
            raise FileNotFoundError(f"Could not find anime-segmentation model at \"{character_model}\". Acquire it from https://github.com/AmusementClub/vs-mlrt/releases/external-models")
        return model
# Zoning information: `character_get_model` is not zoneable.
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------


# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Section: Zones
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Everything set in the previous 4 sections are in the default zones.
# We now collect them into our `zones_spec` dict. You don't need to
# modify anything here.
zones_spec = {}
zone_default = DefaultZone()
zones_spec["default"] = zone_default

# To use different zones for different sections, first, you would need
# to create the zone spec inside this Progression-Boost.py file.
# First, inherit a new zone from `DefaultZone`:
class BuiltinExampleZone(DefaultZone):
# Because we inherited `DefaultZone`, this now has the same settings
# as all the default settings in the previous 4 sections.
# Now we can change the settings that we want to make it different.
# Let's first apply some `--film-grian` because why not:
    def final_dynamic_parameters(self, crf: float) -> list[str]:
        return """--lp 3 --keyint -1 --input-depth 10 --scm 0
                  --tune 3 --luminance-qp-bias 12 --qp-min 8 --chroma-qp-min 10
                  --film-grain 12 --complex-hvs 1 --psy-rd 1.0 --spy-rd 0
                  --color-primaries 1 --transfer-characteristics 1 --matrix-coefficients 1 --color-range 0""".split()
# Let's use a different `--preset` for final encode:
    def metric_dynamic_preset(self, crf: float) -> int:
        return -1
# Change the number of frames measured:
    metric_highest_diff_frames = 5
# Use a different method to measure metric:
    metric_method = "vapoursynth".lower()
# Do some preprocessing:
    def metric_process(self, clips: list[vs.VideoNode]) -> list[vs.VideoNode]:
        for i in range(len(clips)):
            clips[i] = clips[i].std.Crop(left=160, right=160, top=90, bottom=90)
        return clips
# Change to a different `metric_target`:
    metric_target = 0.600
# As you can see, everything can be freely changed. The only exceptions
# are `source_clip` related options in General section, and some scene
# detections options when you're using av1an based scene detection
# methods in Scene Detection section. Search for "Zoning information: "
# in this entire script, and you will find notes regarding how these
# options can or cannot be zoned.
# Now we've finished creating our new zone spec, let's add an instance
# of it in our `zones_spec` dict using the key `builtin_example`:
zones_spec["builtin_example"] = BuiltinExampleZone()
# The key used for each zone can be any name you want, but it must not
# contain whitespace character ` `.

# Just like this, we've added our custom zones to `zones_spec`. To
# referece this zone and actually tell the script when to use each
# zones, use the commandline parameter `--zones` or `--zones-script`.
#
# `--zones` are for zones file.
# The format for zones file are `start_frame end_frame zones_key`.
#   The `end_frame` here is exclusive.
#   The `zones_key` here are the same key we use to add to
#   `zones_spec`.
# An example zones file could look like this:
# ```
# 1000 2000 builtin_example
# 13000 15000 builtin_example
# 25000 28000 builtin_example_2
# ```
# Any regions not covered by zones file will be using the default zone
# at `zones_spec["default"]`.
#
# `--zones-string` is exactly the same as zones file above. Throw away
# the line breaks and put everything on the same line and it will work
# exactly the same.
# The example zones file above is the same as this `--zones-string`:
# `--zones-string "1000 2000 builtin_example 13000 15000 builtin_example 25000 28000 builtin_example_2"`

# Now you can implement your own zone below:


# In the scene detection section, we mentioned that in some works the
# complex scenes are only in OP and ED, but not in the main episode.
# In that case you can set VapourSynth based scene detection as
# default, and then specifically zone the OP or ED with complex scenes
# to use the zone here. This won't be faster, but this will be the
# most efficient way for the encoding.
class BuiltinAv1anZone(DefaultZone):
    scene_detection_method = "av1an".lower()
    # As explained in "Zoning information: " in the section of the
    # guide for scene detection, `scene_detection_av1an_parameters` can
    # only be changed in the default zone.
zones_spec["builtin_av1an"] = BuiltinAv1anZone()
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------


for zone_key in zones_spec:
    if " " in zone_key:
        assert False, f"Key \"{zone_key}\" in `zones_spec` contains whitespace character ` `. The key for all zones must not contain whitespace character"

if zones_file:
    with zones_file.open("r") as zones_f:
        zones_string = zones_f.read()
if zones_string == "":
    if zones_file:
        print(f"\r\033[K\033[31mInput `--zones` is empty. Continuing with no zoning...\033[0m")
    else:
        print(f"\r\033[K\033[31mInput `--zones-string` is empty. Continuing with no zoning...\033[0m")

if zones_string is not None:
    zones_list = []
    zone = []
    zone_head = 0
    for item in zones_string.split():
        if zone_head in [0, 1]:
            try:
                item = int(item)
            except ValueError:
                raise ValueError(f"Invalid zones. Make sure your zones file is correctly written with `start_frame end_frame zones_key`. `zones_key` is not omittable and must not contain whitespaces")
            zone.append(item)
            zone_head += 1
        elif zone_head == 2:
            zone.append(item)
            for i in range(len(zones_list)):
                if zones_list[i][0] > zone[0]:
                    zones_list.insert(i, zone)
                    break
            else:
                zones_list.append(zone)
            zone = []
            zone_head = 0
        else:
            assert False
    if zone_head != 0:
        raise ValueError(f"Invalid zones. There are too much or two few items in the provided zones")
else:
    zones_list = []

zones = []
frame_head = 0
for item in zones_list:
    if item[0] < frame_head:
        raise ValueError(f"Repeating section [{item[0]}:{frame_head}] between input zones.")
    if item[0] > zone_default.source_clip.num_frames - 1:
        print(f"\r\033[KSkipping zones with out of bound start_frame {item[0]}...", end="\n")

    if item[1] <= -2:
        raise ValueError(f"Invalid end_frame in the zones with value {item[1]}")
    if item[1] > zone_default.source_clip.num_frames:
        print(f"\r\033[K\033[31mOut of bound end_frame in the zones with value {item[1]}. Clamp end_frame for the zone to {zone_default.source_clip.num_frames}...\033[0m", end="\n")
        print(f"\r\033[KUse `-1` as end_frame to silence this out of bound warning.", end="\n")
        item[1] = zone_default.source_clip.num_frames
    if item[1] == -1:
        item[1] = zone_default.source_clip.num_frames
        
    if item[1] <= item[0]:
        raise ValueError(f"Invalid zone with start_frame {item[0]} and end_frame {item[1]}.")

    if item[2] not in zones_spec:
        raise ValueError(f"Invalid zone with zone_key \"{item[2]}\". This zone_key \"{item[2]}\" does not exist in `zones_spec`.")

    if item[0] != frame_head:
        zones.append({"start_frame": frame_head,
                      "end_frame": item[0],
                      "zone": zones_spec["default"]})
        frame_head = item[0]
    
    zones.append({"start_frame": item[0],
                  "end_frame": item[1],
                  "zone": zones_spec[item[2]]})
    frame_head = item[1]

if frame_head != zone_default.source_clip.num_frames:
    zones.append({"start_frame": frame_head,
                  "end_frame": zone_default.source_clip.num_frames,
                  "zone": zones_spec["default"]})
    
for zone in zones:
    if zone["zone"].scene_detection_method == "external":
        if not input_scenes_file:
            print("\r\033[K`scene_detection_method` is set to `\"external\"` in at least one of the active zones. `scene_detection_method` of `\"external\"` requires an external scene to be provided via `--input-scenes`. Missing the required `--input-scenes` parameter.", end="\n")
            raise SystemExit(2)
        
        break
else:
    if input_scenes_file:
        print("\r\033[KCommandline parameter `--input-scenes` is provided, but there are no active zones that are using it.", end="\n")

for zone in zones:
    if zone["zone"].metric_enable and zone["zone"].metric_method == "ffvship":
        if probing_input_file != input_file:
            if zone["zone"].metric_continue_filtered_with_ffvship:
                print("\r\033[KYou've set a filtered source to be used for probe encodes via `--encode-input`, but in at least one active zone, `\"ffvship\"` is selected as `metric_method`. `metric_method` of `\"ffvship\"` does not support comparing filtered source against filtered probe encodes. By selecting `\"ffvship\"`, you might be comparing a filtered encode with unfiltered source, which will produce completly unusable metric scores.", end="\n")
            else:
                print("\r\033[KYou've set a filtered source to be used for probe encodes via `--encode-input`, but in at least one active zone, `\"ffvship\"` is selected as `metric_method`. `metric_method` of `\"ffvship\"` does not support comparing filtered source against filtered probe encodes. By selecting `\"ffvship\"`, you're now comparing a filtered encode with unfiltered source, which will produce completly unusable metric scores. You should switch to a VapourSynth based methods, and then copy in your filtering chain for `metric_reference`.", end="\n")
                print("\r\033[KProgression Boost will quit now, but if you know what you're doing, you may let it continue by setting `metric_continue_filtered_with_ffvship` for the related zones.", end="\n")
                raise SystemExit(2)

        break

for zone in zones:
    if zone["zone"].metric_enable and zone["zone"].probing_preset < 6:
        print("\r\033[KProbing with slower `--preset` than `--preset 6` is not tested, and Progression Boost's `--preset` readjustment feature may not work properly. Using slower `--preset` than `--preset 7` does not yield any meaningful improvements, and you should use `--preset 7` instead.", end="\n")

        break

for zone in zones:
    if zone["zone"].character_enable:
        character_backend = zone_default.character_get_backend()
        character_model = zone_default.character_get_model()

        break
for zone in zones:
    if zone["zone"].character_enable and zone["zone"].character_max_roi_boost:
        if not roi_maps_dir:
            print("\r\033[KCharacter Boost is enabled in at least one active zone, but commandline parameter `--output-roi-map` is not provided.", end="\n")
            raise SystemExit(2)
        roi_maps_dir.mkdir(parents=True, exist_ok=True)

        break


# ---------------------------------------------------------------------
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
# ---------------------------------------------------------------------


print(f"\r\033[KTime {datetime.now().time().isoformat(timespec="seconds")} / Progression Boost started", end="\n")


#  ███████╗ ██████╗███████╗███╗   ██╗███████╗    ██████╗ ███████╗████████╗███████╗ ██████╗████████╗██╗ ██████╗ ███╗   ██╗
#  ██╔════╝██╔════╝██╔════╝████╗  ██║██╔════╝    ██╔══██╗██╔════╝╚══██╔══╝██╔════╝██╔════╝╚══██╔══╝██║██╔═══██╗████╗  ██║
#  ███████╗██║     █████╗  ██╔██╗ ██║█████╗      ██║  ██║█████╗     ██║   █████╗  ██║        ██║   ██║██║   ██║██╔██╗ ██║
#  ╚════██║██║     ██╔══╝  ██║╚██╗██║██╔══╝      ██║  ██║██╔══╝     ██║   ██╔══╝  ██║        ██║   ██║██║   ██║██║╚██╗██║
#  ███████║╚██████╗███████╗██║ ╚████║███████╗    ██████╔╝███████╗   ██║   ███████╗╚██████╗   ██║   ██║╚██████╔╝██║ ╚████║
#  ╚══════╝ ╚═════╝╚══════╝╚═╝  ╚═══╝╚══════╝    ╚═════╝ ╚══════╝   ╚═╝   ╚══════╝ ╚═════╝   ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
#
#  ANSI Shadow ANSI FIGlet font


scene_detection_scenes_file = scene_detection_temp_dir.joinpath("scenes.json")
scene_detection_av1an_scenes_file = scene_detection_temp_dir.joinpath("av1an.scenes.json")
scene_detection_diffs_file = scene_detection_temp_dir.joinpath("luma-diff.txt")
scene_detection_average_file = scene_detection_temp_dir.joinpath("luma-average.txt")
scene_detection_min_file = scene_detection_temp_dir.joinpath("luma-min.txt")
scene_detection_max_file = scene_detection_temp_dir.joinpath("luma-max.txt")

scene_detection_diffs_available = False
if resume and scene_detection_diffs_file.exists() and \
              scene_detection_average_file.exists() and \
              scene_detection_min_file.exists() and \
              scene_detection_max_file.exists():
    scene_detection_diffs = np.loadtxt(scene_detection_diffs_file, dtype=np.float32)
    scene_detection_average = np.loadtxt(scene_detection_average_file, dtype=np.float32)
    scene_detection_min = np.loadtxt(scene_detection_min_file, dtype=np.float32)
    scene_detection_max = np.loadtxt(scene_detection_max_file, dtype=np.float32)
    scene_detection_diffs_available = True


frame_rjust_digits = math.floor(np.log10(zone_default.source_clip.num_frames)) + 1
frame_print = lambda frame: f"Frame {frame}"
frame_rjust = lambda frame: str(frame).rjust(frame_rjust_digits)
frame_scene_print = lambda start_frame, end_frame: f"Scene [{frame_rjust(start_frame)}:{frame_rjust(end_frame)}]"


if not resume or not scene_detection_scenes_file.exists():
    for zone in zones:
        if zone["zone"].scene_detection_method == "av1an":
            if not resume or not scene_detection_av1an_scenes_file.exists():
                scene_detection_perform_av1an = True
            else:
                scene_detection_perform_av1an = False

            scene_detection_has_av1an = True
            break
    else:
        scene_detection_has_av1an = False
        scene_detection_perform_av1an = False
    for zone in zones:
        if zone["zone"].scene_detection_method == "vapoursynth":
            scene_detection_perform_vapoursynth = True
            break
    else:
        scene_detection_perform_vapoursynth = False
    for zone in zones:
        if zone["zone"].scene_detection_method == "external":
            scene_detection_has_external = True
            break
    else:
        scene_detection_has_external = False

    if scene_detection_perform_av1an:
        scene_detection_av1an_scenes_file.unlink(missing_ok=True)

        scene_detection_av1an_force_keyframes = []
        for zone in zones:
            scene_detection_av1an_force_keyframes.append(str(zone["start_frame"]))
        command = [
            "av1an",
            "--temp", scene_detection_temp_dir.joinpath("av1an.tmp"),
            "-i", input_file,
            "--scenes", scene_detection_av1an_scenes_file,
            *zone_default.scene_detection_av1an_parameters(),
            "--force-keyframes", ",".join(scene_detection_av1an_force_keyframes)
        ]
        scene_detection_process = subprocess.Popen(command, text=True)

        
    def scene_detection_measure_frame_luma():
        global scene_detection_diffs
        global scene_detection_average
        global scene_detection_min
        global scene_detection_max
        global scene_detection_diffs_available

        scene_detection_luma_clip = zone_default.source_clip
        scene_detection_luma_clip = scene_detection_luma_clip.std.PlaneStats(scene_detection_luma_clip[0] + scene_detection_luma_clip, plane=0, prop="Luma")
        
        start = time() - 0.000001
        scene_detection_diffs = np.empty((scene_detection_luma_clip.num_frames,), dtype=np.float32)
        scene_detection_average = np.empty((scene_detection_luma_clip.num_frames,), dtype=np.float32)
        scene_detection_min = np.empty((scene_detection_luma_clip.num_frames,), dtype=np.float32)
        scene_detection_max = np.empty((scene_detection_luma_clip.num_frames,), dtype=np.float32)
        for current_frame, frame in enumerate(scene_detection_luma_clip.frames(backlog=48)):
            print(f"\r\033[K{frame_print(current_frame)} / Measuring frame luminance / {current_frame / (time() - start):.2f} fps", end="\r")
            scene_detection_diffs[current_frame] = frame.props["LumaDiff"]
            scene_detection_average[current_frame] = frame.props["LumaAverage"]
            scene_detection_min[current_frame] = frame.props["LumaMin"]
            scene_detection_max[current_frame] = frame.props["LumaMax"]
        print(f"\r\033[K{frame_print(current_frame + 1)} / Frame luminance measurement complete / {(current_frame + 1) / (time() - start):.2f} fps", end="\n")
        
        np.savetxt(scene_detection_diffs_file, scene_detection_diffs, fmt="%.9f")
        np.savetxt(scene_detection_average_file, scene_detection_average, fmt="%.9f")
        np.savetxt(scene_detection_min_file, scene_detection_min, fmt="%.9f")
        np.savetxt(scene_detection_max_file, scene_detection_max, fmt="%.9f")
        scene_detection_diffs_available = True

    if not scene_detection_diffs_available:
        if scene_detection_perform_av1an or \
           not (scene_detection_perform_vapoursynth and not scene_detection_has_av1an and not scene_detection_has_external):
            scene_detection_measure_frame_luma()

    
    if scene_detection_perform_vapoursynth:
        if not scene_detection_diffs_available:
            scene_detection_diffs = np.empty((zone_default.source_clip.num_frames,), dtype=np.float32)
            scene_detection_average = np.empty((zone_default.source_clip.num_frames,), dtype=np.float32)
            scene_detection_min = np.empty((zone_default.source_clip.num_frames,), dtype=np.float32)
            scene_detection_max = np.empty((zone_default.source_clip.num_frames,), dtype=np.float32)

        scene_detection_clip_base = zone_default.source_clip
        scene_detection_bits = scene_detection_clip_base.format.bits_per_sample

        if not scene_detection_diffs_available:
            scene_detection_clip_base = scene_detection_clip_base.std.PlaneStats(scene_detection_clip_base[0] + scene_detection_clip_base, plane=0, prop="Luma")
        
        target_width = np.round(np.sqrt(1280 * 720 / scene_detection_clip_base.width / scene_detection_clip_base.height) * scene_detection_clip_base.width / 40) * 40
        if target_width < scene_detection_clip_base.width * 0.9:
            target_height = np.ceil(target_width / scene_detection_clip_base.width * scene_detection_clip_base.height / 2) * 2
            src_height = target_height / target_width * scene_detection_clip_base.width
            src_top = (scene_detection_clip_base.height - src_height) / 2
            scene_detection_clip_base = scene_detection_clip_base.resize.Point(width=target_width, height=target_height, src_top=src_top, src_height=src_height,
                                                                               format=vs.YUV420P8, dither_type="none")

        zones_diffs = {}
        for zone_i, zone in enumerate(zones):
            assert zone["zone"].scene_detection_method in ["av1an", "vapoursynth", "external"], "Invalid `scene_detection_method`. Please check your config inside `Progression-Boost.py`."

            if zone["zone"].scene_detection_method == "vapoursynth":
                assert zone["zone"].scene_detection_vapoursynth_method in ["wwxd", "wwxd_scxvid"], "Invalid `scene_detection_vapoursynth_method`. Please check your config inside `Progression-Boost.py`."
                assert zone["zone"].scene_detection_vapoursynth_range in ["limited", "full"], "Invalid `scene_detection_vapoursynth_range`. Please check your config inside `Progression-Boost.py`."
                assert zone["zone"].scene_detection_extra_split >= zone["zone"].scene_detection_min_scene_len * 2, "`scene_detection_method` `vapoursynth` does not support `scene_detection_extra_split` to be smaller than 2 times `scene_detection_min_scene_len`."

                scene_detection_clip = scene_detection_clip_base[zone["start_frame"]:zone["end_frame"]]
                scene_detection_clip = scene_detection_clip.wwxd.WWXD()
                if zone["zone"].scene_detection_vapoursynth_method == "wwxd_scxvid":
                    scene_detection_clip = scene_detection_clip.scxvid.Scxvid()

                diffs = np.empty((scene_detection_clip.num_frames,), dtype=float)
                luma_scenecut_prev = True

                start = time() - 0.000001
                for offset_frame, frame in enumerate(scene_detection_clip.frames(backlog=48)):
                    current_frame = zone["start_frame"] + offset_frame
                    print(f"\r\033[K{frame_print(current_frame)} / Detecting scenes / {offset_frame / (time() - start):.2f} fps", end="")

                    if not scene_detection_diffs_available:
                        scene_detection_diffs[current_frame] = frame.props["LumaDiff"]
                        scene_detection_average[current_frame] = frame.props["LumaAverage"]
                        scene_detection_min[current_frame] = frame.props["LumaMin"]
                        scene_detection_max[current_frame] = frame.props["LumaMax"]

                    if zone["zone"].scene_detection_vapoursynth_method == "wwxd":
                        scene_detection_scenecut = frame.props["Scenechange"] == 1
                    elif zone["zone"].scene_detection_vapoursynth_method == "wwxd_scxvid":
                        scene_detection_scenecut = (frame.props["Scenechange"] == 1) + (frame.props["_SceneChangePrev"] == 1) / 2
                    if zone["zone"].scene_detection_vapoursynth_range == "limited":
                        luma_scenecut = scene_detection_min[current_frame] > 231.125 * 2 ** (scene_detection_bits - 8) or \
                                        scene_detection_max[current_frame] < 19.875 * 2 ** (scene_detection_bits - 8)
                    elif zone["zone"].scene_detection_vapoursynth_range == "full":
                        luma_scenecut = scene_detection_min[current_frame] > 251.125 * 2 ** (scene_detection_bits - 8) or \
                                        scene_detection_max[current_frame] < 3.875 * 2 ** (scene_detection_bits - 8)

                    if luma_scenecut or luma_scenecut_prev:
                        diffs[offset_frame] = scene_detection_diffs[current_frame] + 1.17
                    else:
                        diffs[offset_frame] = scene_detection_diffs[current_frame] + scene_detection_scenecut

                    luma_scenecut_prev = luma_scenecut

                zones_diffs[zone_i] = diffs

        print(f"\r\033[K{frame_print(current_frame + 1)} / VapourSynth based scene detection complete", end="\n")

    if scene_detection_has_external:
        with input_scenes_file.open("r") as input_scenes_f:
            try:
                scene_detection_external_scenes = json.load(input_scenes_f)
            except:
                raise ValueError("Invalid scenes file from `--input-scenes`")
        assert "scenes" in scene_detection_external_scenes, "Invalid scenes file from `--input-scenes`"


    if scene_detection_perform_av1an:
        scene_detection_process.wait()
        if scene_detection_process.returncode != 0:
            raise subprocess.CalledProcessError

        assert scene_detection_av1an_scenes_file.exists(), "Unexpected result from av1an"

    if scene_detection_has_av1an:
        with scene_detection_av1an_scenes_file.open("r") as av1an_scenes_f:
            scene_detection_av1an_scenes = json.load(av1an_scenes_f)

        assert scene_detection_av1an_scenes["frames"] == zone_default.source_clip.num_frames, "Unexpected result from av1an"
        if "split_scenes" in scene_detection_av1an_scenes:
            scene_detection_av1an_scenes["scenes"] = scene_detection_av1an_scenes["split_scenes"]
        assert "scenes" in scene_detection_av1an_scenes, "Unexpected result from av1an"


    scenes = {}
    scenes["frames"] = zone_default.source_clip.num_frames
    scenes["scenes"] = []
    for zone_i, zone in enumerate(zones):
        if zone["zone"].scene_detection_method == "av1an":
            av1an_scenes_start_copying = False
            for av1an_scene in scene_detection_av1an_scenes["scenes"]:
                if av1an_scene["start_frame"] == zone["start_frame"]:
                    av1an_scenes_start_copying = True
                assert (av1an_scene["start_frame"] >= zone["start_frame"]) == av1an_scenes_start_copying, "Unexpected result from av1an"
                if av1an_scene["start_frame"] == zone["end_frame"]:
                    break
                assert av1an_scene["start_frame"] < zone["end_frame"], "Unexpected result from av1an"

                if av1an_scenes_start_copying:
                    print(f"\r\033[K{frame_scene_print(av1an_scene["start_frame"], av1an_scene["end_frame"])} / Creating scenes", end="")
                    scenes["scenes"].append(av1an_scene)

        elif zone["zone"].scene_detection_method == "external":
            external_scenes_start_copying = False
            last_end_frame = None
            for external_scene in scene_detection_external_scenes["scenes"]:
                assert "start_frame" in external_scene and "end_frame" in external_scene, "Invalid scenes file from `--input-scenes`"

                if external_scene["start_frame"] >= zone["start_frame"]:
                    if not external_scenes_start_copying and external_scene["start_frame"] > zone["start_frame"]:
                        if not zone["zone"].metric_enable and external_scene["end_frame"] - zone["start_frame"] < 5:
                            print(f"\r\033[K[{frame_scene_print(zone["start_frame"], external_scene["end_frame"])} / A scene from `--input-scenes` is cut off by zone boundary into a scene shorter than 5 frames. As Progression Boost module is disabled for the zone, this scene might get poorly encoded.", end="\n")
                
                        scenes["scenes"].append({"start_frame": zone["start_frame"],
                                                 "end_frame": external_scene["start_frame"],
                                                 "zone_overrides": None})
                                                 
                    external_scenes_start_copying = True

                if external_scenes_start_copying:
                    if last_end_frame is not None:
                        assert last_end_frame == external_scene["start_frame"], "Invalid scenes file from `--input-scenes`. Scenes file not continuous."
                    last_end_frame = external_scene["end_frame"]
                    assert external_scene["end_frame"] > external_scene["start_frame"], "Invalid scenes file from `--input-scenes`"

                    if external_scene["end_frame"] > zone["end_frame"]:
                        if not zone["zone"].metric_enable and zone["end_frame"] - external_scene["start_frame"] < 5:
                            print(f"\r\033[K{frame_scene_print(external_scene["start_frame"], zone["end_frame"])} / A scene from `--input-scenes` is cut off by zone boundary into a scene shorter than 5 frames. As Progression Boost module is disabled for the zone, this scene might get poorly encoded.", end="\n")
                        print(f"\r\033[K{frame_scene_print(external_scene["start_frame"], zone["end_frame"])} / Creating scenes", end="")
                        scenes["scenes"].append({"start_frame": external_scene["start_frame"],
                                                 "end_frame": zone["end_frame"],
                                                 "zone_overrides": None})
                    else:
                        print(f"\r\033[K{frame_scene_print(external_scene["start_frame"], external_scene["end_frame"])} / Creating scenes", end="")
                        scenes["scenes"].append({"start_frame": external_scene["start_frame"],
                                                 "end_frame": external_scene["end_frame"],
                                                 "zone_overrides": None})

                if external_scene["end_frame"] >= zone["end_frame"]:
                    break
            else:
                raise ValueError("Invalid scenes file from `--input-scenes`. There are no scenes in the scenes file that reach the end of the zone")

        elif zone["zone"].scene_detection_method == "vapoursynth":
            diffs = zones_diffs[zone_i]
            diffs_sort = np.argsort(diffs, stable=True)[::-1]

            def scene_detection_split_scene(start_frame, end_frame):
                print(f"\r\033[K{frame_scene_print(start_frame + zone["start_frame"], end_frame + zone["start_frame"])} / Creating scenes", end="")


                if end_frame - start_frame <= zone["zone"].scene_detection_target_split or \
                   end_frame - start_frame < 2 * zone["zone"].scene_detection_min_scene_len:
                    if verbose >= 2:
                        print(f" / branch complete", end="\n")
                    return [start_frame]


                if end_frame - start_frame <= 2 * zone["zone"].scene_detection_target_split:
                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len and \
                           current_frame - start_frame <= zone["zone"].scene_detection_target_split and end_frame - current_frame <= zone["zone"].scene_detection_target_split and \
                           ((current_frame - start_frame) % 32 == 1 or (end_frame - current_frame) % 32 == 1):
                            if verbose >= 2:
                                print(f" / split / 32-frame hierarchical structure flavoured / target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)
                                   
                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len and \
                           current_frame - start_frame <= zone["zone"].scene_detection_target_split and end_frame - current_frame <= zone["zone"].scene_detection_target_split and \
                           ((current_frame - start_frame) % 16 == 1 or (end_frame - current_frame) % 16 == 1):
                            if verbose >= 2:
                                print(f" / split / 16-frame hierarchical structure flavoured / target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)
                                   
                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len and \
                           current_frame - start_frame <= zone["zone"].scene_detection_target_split and end_frame - current_frame <= zone["zone"].scene_detection_target_split and \
                           ((current_frame - start_frame) % 8 == 1 or (end_frame - current_frame) % 8 == 1):
                            if verbose >= 2:
                                print(f" / split / 8-frame hierarchical structure flavoured / target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)
                                   
                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len and \
                           current_frame - start_frame <= zone["zone"].scene_detection_target_split and end_frame - current_frame <= zone["zone"].scene_detection_target_split and \
                           ((current_frame - start_frame) % 4 == 1 or (end_frame - current_frame) % 4 == 1):
                            if verbose >= 2:
                                print(f" / split / 4-frame hierarchical structure flavoured / target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)
                                   
                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.17:
                            break
                        if current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len and \
                           current_frame - start_frame <= zone["zone"].scene_detection_target_split and end_frame - current_frame <= zone["zone"].scene_detection_target_split and \
                           ((current_frame - start_frame) % 2 == 1 or (end_frame - current_frame) % 2 == 1):
                            if verbose >= 2:
                                print(f" / split / 2-frame hierarchical structure flavoured / target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.18:
                            break
                        if current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len and \
                           current_frame - start_frame <= zone["zone"].scene_detection_target_split and end_frame - current_frame <= zone["zone"].scene_detection_target_split:
                            if verbose >= 2:
                                print(f" / split / target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)


                if end_frame - start_frame <= zone["zone"].scene_detection_extra_split:
                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame <= zone["zone"].scene_detection_target_split and (current_frame - start_frame) % 32 == 1) or \
                            (end_frame - current_frame <= zone["zone"].scene_detection_target_split and (end_frame - current_frame) % 32 == 1)):
                            if verbose >= 2:
                                print(f" / split / 32-frame hierarchical structure flavoured / singleside target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame <= zone["zone"].scene_detection_target_split and (current_frame - start_frame) % 16 == 1) or \
                            (end_frame - current_frame <= zone["zone"].scene_detection_target_split and (end_frame - current_frame) % 16 == 1)):
                            if verbose >= 2:
                                print(f" / split / 16-frame hierarchical structure flavoured / singleside target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame <= zone["zone"].scene_detection_target_split and (current_frame - start_frame) % 8 == 1) or \
                            (end_frame - current_frame <= zone["zone"].scene_detection_target_split and (end_frame - current_frame) % 8 == 1)):
                            if verbose >= 2:
                                print(f" / split / 8-frame hierarchical structure flavoured / singleside target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame <= zone["zone"].scene_detection_target_split and (current_frame - start_frame) % 4 == 1) or \
                            (end_frame - current_frame <= zone["zone"].scene_detection_target_split and (end_frame - current_frame) % 4 == 1)):
                            if verbose >= 2:
                                print(f" / split / 4-frame hierarchical structure flavoured / singleside target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.17:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame <= zone["zone"].scene_detection_target_split and (current_frame - start_frame) % 2 == 1) or \
                            (end_frame - current_frame <= zone["zone"].scene_detection_target_split and (end_frame - current_frame) % 2 == 1)):
                            if verbose >= 2:
                                print(f" / split / 2-frame hierarchical structure flavoured / singleside target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)


                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.17:
                            break
                        if current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len and \
                           ((current_frame - start_frame) % 32 == 1 or (end_frame - current_frame) % 32 == 1):
                            if verbose >= 2:
                                print(f" / split / 32-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len and \
                           ((current_frame - start_frame) % 16 == 1 or (end_frame - current_frame) % 16 == 1):
                            if verbose >= 2:
                                print(f" / split / 16-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len and \
                           ((current_frame - start_frame) % 8 == 1 or (end_frame - current_frame) % 8 == 1):
                            if verbose >= 2:
                                print(f" / split / 8-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len and \
                           ((current_frame - start_frame) % 4 == 1 or (end_frame - current_frame) % 4 == 1):
                            if verbose >= 2:
                                print(f" / split / 4-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.17:
                            break
                        if current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len and \
                           ((current_frame - start_frame) % 2 == 1 or (end_frame - current_frame) % 2 == 1):
                            if verbose >= 2:
                                print(f" / split / 2-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)


                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.18:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           (current_frame - start_frame <= 2 * zone["zone"].scene_detection_target_split or end_frame - current_frame <= 2 * zone["zone"].scene_detection_target_split):
                            if verbose >= 2:
                                print(f" / split / singleside 2 times target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)


                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.18:
                            if verbose >= 2:
                                print(f" / branch complete", end="\n")
                            return [start_frame]
                        if current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len:
                            if verbose >= 2:
                                print(f" / split / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)


                else: # end_frame - start_frame > zone["zone"].scene_detection_extra_split
                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.24:
                            break
                        if current_frame - start_frame >= zone["zone"].scene_detection_extra_split and end_frame - current_frame >= zone["zone"].scene_detection_extra_split and \
                           ((current_frame - start_frame) % 2 == 1 or (end_frame - current_frame) % 2 == 1) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.25):
                            if verbose >= 2:
                                print(f" / extra_split split / doubleside extra_split flavoured / hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.24:
                            break
                        if current_frame - start_frame >= zone["zone"].scene_detection_extra_split and end_frame - current_frame >= zone["zone"].scene_detection_extra_split and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.15):
                            if verbose >= 2:
                                print(f" / extra_split split / doubleside extra_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)


                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame > 2 * zone["zone"].scene_detection_target_split and end_frame - current_frame > 2 * zone["zone"].scene_detection_target_split) and \
                           ((current_frame - start_frame) % 32 == 1 or (end_frame - current_frame) % 32 == 1) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.20):
                            if verbose >= 2:
                                print(f" / extra_split split / 32-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame > 2 * zone["zone"].scene_detection_target_split and end_frame - current_frame > 2 * zone["zone"].scene_detection_target_split) and \
                           ((current_frame - start_frame) % 16 == 1 or (end_frame - current_frame) % 16 == 1) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.20):
                            if verbose >= 2:
                                print(f" / extra_split split / 16-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame > 2 * zone["zone"].scene_detection_target_split and end_frame - current_frame > 2 * zone["zone"].scene_detection_target_split) and \
                           ((current_frame - start_frame) % 8 == 1 or (end_frame - current_frame) % 8 == 1) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.20):
                            if verbose >= 2:
                                print(f" / extra_split split / 8-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame > 2 * zone["zone"].scene_detection_target_split and end_frame - current_frame > 2 * zone["zone"].scene_detection_target_split) and \
                           ((current_frame - start_frame) % 4 == 1 or (end_frame - current_frame) % 4 == 1) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.20):
                            if verbose >= 2:
                                print(f" / extra_split split / 4-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.17:
                            break
                        if (current_frame - start_frame > 2 * zone["zone"].scene_detection_target_split and end_frame - current_frame > 2 * zone["zone"].scene_detection_target_split) and \
                           ((current_frame - start_frame) % 2 == 1 or (end_frame - current_frame) % 2 == 1) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.20):
                            if verbose >= 2:
                                print(f" / extra_split split / 2-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)


                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame <= zone["zone"].scene_detection_target_split and (current_frame - start_frame) % 32 == 1) or \
                            (end_frame - current_frame <= zone["zone"].scene_detection_target_split and (end_frame - current_frame) % 32 == 1)):
                            if verbose >= 2:
                                print(f" / extra_split split / 32-frame hierarchical structure flavoured / singleside target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)
                                   
                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame <= zone["zone"].scene_detection_target_split and (current_frame - start_frame) % 16 == 1) or \
                            (end_frame - current_frame <= zone["zone"].scene_detection_target_split and (end_frame - current_frame) % 16 == 1)):
                            if verbose >= 2:
                                print(f" / extra_split split / 16-frame hierarchical structure flavoured / singleside target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)
                                   
                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame <= zone["zone"].scene_detection_target_split and (current_frame - start_frame) % 8 == 1) or \
                            (end_frame - current_frame <= zone["zone"].scene_detection_target_split and (end_frame - current_frame) % 8 == 1)):
                            if verbose >= 2:
                                print(f" / extra_split split / 8-frame hierarchical structure flavoured / singleside target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)
                                   
                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame <= zone["zone"].scene_detection_target_split and (current_frame - start_frame) % 4 == 1) or \
                            (end_frame - current_frame <= zone["zone"].scene_detection_target_split and (end_frame - current_frame) % 4 == 1)):
                            if verbose >= 2:
                                print(f" / extra_split split / 4-frame hierarchical structure flavoured / singleside target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)
                                   
                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.17:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame <= zone["zone"].scene_detection_target_split and (current_frame - start_frame) % 2 == 1) or \
                            (end_frame - current_frame <= zone["zone"].scene_detection_target_split and (end_frame - current_frame) % 2 == 1)):
                            if verbose >= 2:
                                print(f" / extra_split split / 2-frame hierarchical structure flavoured / singleside target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                                   
                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame <= 2 * zone["zone"].scene_detection_target_split and (current_frame - start_frame) % 32 == 1) or \
                            (end_frame - current_frame <= 2 * zone["zone"].scene_detection_target_split and (end_frame - current_frame) % 32 == 1)):
                            if verbose >= 2:
                                print(f" / extra_split split / 32-frame hierarchical structure flavoured / singleside 2 times target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)
                                   
                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame <= 2 * zone["zone"].scene_detection_target_split and (current_frame - start_frame) % 16 == 1) or \
                            (end_frame - current_frame <= 2 * zone["zone"].scene_detection_target_split and (end_frame - current_frame) % 16 == 1)):
                            if verbose >= 2:
                                print(f" / extra_split split / 16-frame hierarchical structure flavoured / singleside 2 times target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)
                                   
                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame <= 2 * zone["zone"].scene_detection_target_split and (current_frame - start_frame) % 8 == 1) or \
                            (end_frame - current_frame <= 2 * zone["zone"].scene_detection_target_split and (end_frame - current_frame) % 8 == 1)):
                            if verbose >= 2:
                                print(f" / extra_split split / 8-frame hierarchical structure flavoured / singleside 2 times target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)
                                   
                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame <= 2 * zone["zone"].scene_detection_target_split and (current_frame - start_frame) % 4 == 1) or \
                            (end_frame - current_frame <= 2 * zone["zone"].scene_detection_target_split and (end_frame - current_frame) % 4 == 1)):
                            if verbose >= 2:
                                print(f" / extra_split split / 4-frame hierarchical structure flavoured / singleside 2 times target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)
                                   
                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.17:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame <= 2 * zone["zone"].scene_detection_target_split and (current_frame - start_frame) % 2 == 1) or \
                            (end_frame - current_frame <= 2 * zone["zone"].scene_detection_target_split and (end_frame - current_frame) % 2 == 1)):
                            if verbose >= 2:
                                print(f" / extra_split split / 2-frame hierarchical structure flavoured / singleside 2 times target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)


                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 1.19:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           (current_frame - start_frame <= 2 * zone["zone"].scene_detection_target_split or end_frame - current_frame <= 2 * zone["zone"].scene_detection_target_split):
                            if verbose >= 2:
                                print(f" / extra_split split / singleside 2 times target_split flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)


                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 0.99:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame) % 32 == 1 or (end_frame - current_frame) % 32 == 1) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.20):
                            if verbose >= 2:
                                print(f" / extra_split split / low scenechange / 32-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 0.99:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame) % 16 == 1 or (end_frame - current_frame) % 16 == 1) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.20):
                            if verbose >= 2:
                                print(f" / extra_split split / low scenechange / 16-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 0.99:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame) % 8 == 1 or (end_frame - current_frame) % 8 == 1) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.20):
                            if verbose >= 2:
                                print(f" / extra_split split / low scenechange / 8-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 0.99:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame) % 4 == 1 or (end_frame - current_frame) % 4 == 1) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.20):
                            if verbose >= 2:
                                print(f" / extra_split split / low scenechange / 4-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 0.99:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame) % 2 == 1 or (end_frame - current_frame) % 2 == 1) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.20):
                            if verbose >= 2:
                                print(f" / extra_split split / low scenechange / 2-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)


                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 0.09:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame) % 32 == 1 or (end_frame - current_frame) % 32 == 1) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.05):
                            if verbose >= 2:
                                print(f" / extra_split split / low scenechange / 32-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 0.09:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame) % 16 == 1 or (end_frame - current_frame) % 16 == 1) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.05):
                            if verbose >= 2:
                                print(f" / extra_split split / low scenechange / 16-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 0.09:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame) % 8 == 1 or (end_frame - current_frame) % 8 == 1) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.05):
                            if verbose >= 2:
                                print(f" / extra_split split / low scenechange / 8-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 0.09:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame) % 4 == 1 or (end_frame - current_frame) % 4 == 1) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.05):
                            if verbose >= 2:
                                print(f" / extra_split split / low scenechange / 4-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if diffs[current_frame] < 0.09:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           ((current_frame - start_frame) % 2 == 1 or (end_frame - current_frame) % 2 == 1) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.05):
                            if verbose >= 2:
                                print(f" / extra_split split / low scenechange / 2-frame hierarchical structure flavoured / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)


                    for current_frame in diffs_sort:
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split):
                            if verbose >= 2:
                                print(f" / extra_split split / low scenechange / frame {current_frame} / diff {np.floor(diffs[current_frame] * 100) / 100:.2f}", end="\n")
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)


                assert False, "This indicates a bug in the original code. Please report this to the repository including this entire error message."

            start_frames = scene_detection_split_scene(0, len(diffs))

            start_frames += [zone["end_frame"] - zone["start_frame"]]
            for i in range(len(start_frames) - 1):
                scenes["scenes"].append({"start_frame": start_frames[i] + zone["start_frame"],
                                         "end_frame": start_frames[i + 1] + zone["start_frame"],
                                         "zone_overrides": None})

    print(f"\r\033[K{frame_scene_print(scenes["scenes"][-1]["start_frame"], scenes["scenes"][-1]["end_frame"])} / Scene creation complete", end="\n")

    with scene_detection_scenes_file.open("w") as scenes_f:
        json.dump(scenes, scenes_f, cls=NumpyEncoder)

    if not scene_detection_diffs_available:
        np.savetxt(scene_detection_diffs_file, scene_detection_diffs, fmt="%.9f")
        np.savetxt(scene_detection_average_file, scene_detection_average, fmt="%.9f")
        np.savetxt(scene_detection_min_file, scene_detection_min, fmt="%.9f")
        np.savetxt(scene_detection_max_file, scene_detection_max, fmt="%.9f")
        scene_detection_diffs_available = True

    if scene_detection_perform_vapoursynth:
        print(f"\r\033[KTime {datetime.now().time().isoformat(timespec="seconds")} / Scene detection finished", end="\n")

    for dir_ in [progression_boost_temp_dir, character_boost_temp_dir]:
        shutil.rmtree(dir_, ignore_errors=True)
        dir_.mkdir(parents=True, exist_ok=True)
else:
    with scene_detection_scenes_file.open("r") as scenes_f:
        scenes = json.load(scenes_f)


for zone in zones:
    if zone["zone"].metric_enable:
        metric_has_metric = True
        break
else:
    metric_has_metric = False
for zone in zones:
    if zone["zone"].character_enable:
        character_has_character = True
        break
else:
    character_has_character = False


zone_scenes = copy.deepcopy(scenes)
zone_head = 0
for zone_scene in zone_scenes["scenes"]:
    if resume:
        assert zone_scene["start_frame"] <= zones[zone_head]["end_frame"], "Scene detection scenes misaligned with zones. Try run Progression Boost fresh without `--resume`. If this issue persists, Please report this to the repository including this entire error message."
    else:
        assert zone_scene["start_frame"] <= zones[zone_head]["end_frame"], "This indicates a bug in the original code. Please report this to the repository including this entire error message."
    if zone_scene["start_frame"] == zones[zone_head]["end_frame"]:
        zone_head += 1

    zone_scene["zone"] = zones[zone_head]["zone"]

    zone_scene["zone_overrides"] = {
        "encoder": "svt_av1",
        "passes": 1,
        "extra_splits_len": zone_scene["zone"].scene_detection_extra_split,
        "min_scene_len": zone_scene["zone"].scene_detection_min_scene_len
    }


#  ██████╗ ██████╗  ██████╗ ██████╗ ██╗███╗   ██╗ ██████╗       ███████╗██╗██████╗ ███████╗████████╗
#  ██╔══██╗██╔══██╗██╔═══██╗██╔══██╗██║████╗  ██║██╔════╝       ██╔════╝██║██╔══██╗██╔════╝╚══██╔══╝
#  ██████╔╝██████╔╝██║   ██║██████╔╝██║██╔██╗ ██║██║  ███╗█████╗█████╗  ██║██████╔╝███████╗   ██║   
#  ██╔═══╝ ██╔══██╗██║   ██║██╔══██╗██║██║╚██╗██║██║   ██║╚════╝██╔══╝  ██║██╔══██╗╚════██║   ██║   
#  ██║     ██║  ██║╚██████╔╝██████╔╝██║██║ ╚████║╚██████╔╝      ██║     ██║██║  ██║███████║   ██║   
#  ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝       ╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝   


scene_rjust_digits = math.floor(np.log10(len(scenes["scenes"]))) + 1
scene_rjust = lambda scene: str(scene).rjust(scene_rjust_digits, "0")
scene_frame_print = lambda scene: f"Scene {scene_rjust(scene)} Frame [{frame_rjust(scenes["scenes"][scene]["start_frame"])}:{frame_rjust(scenes["scenes"][scene]["end_frame"])}]"


dc = np.array([
    4,    9,    10,   13,   15,   17,   20,   22,   25,   28,   31,   34,   37,   40,   43,   47,   50,   53,   57,
    60,   64,   68,   71,   75,   78,   82,   86,   90,   93,   97,   101,  105,  109,  113,  116,  120,  124,  128,
    132,  136,  140,  143,  147,  151,  155,  159,  163,  166,  170,  174,  178,  182,  185,  189,  193,  197,  200,
    204,  208,  212,  215,  219,  223,  226,  230,  233,  237,  241,  244,  248,  251,  255,  259,  262,  266,  269,
    273,  276,  280,  283,  287,  290,  293,  297,  300,  304,  307,  310,  314,  317,  321,  324,  327,  331,  334,
    337,  343,  350,  356,  362,  369,  375,  381,  387,  394,  400,  406,  412,  418,  424,  430,  436,  442,  448,
    454,  460,  466,  472,  478,  484,  490,  499,  507,  516,  525,  533,  542,  550,  559,  567,  576,  584,  592,
    601,  609,  617,  625,  634,  644,  655,  666,  676,  687,  698,  708,  718,  729,  739,  749,  759,  770,  782,
    795,  807,  819,  831,  844,  856,  868,  880,  891,  906,  920,  933,  947,  961,  975,  988,  1001, 1015, 1030,
    1045, 1061, 1076, 1090, 1105, 1120, 1137, 1153, 1170, 1186, 1202, 1218, 1236, 1253, 1271, 1288, 1306, 1323, 1342,
    1361, 1379, 1398, 1416, 1436, 1456, 1476, 1496, 1516, 1537, 1559, 1580, 1601, 1624, 1647, 1670, 1692, 1717, 1741,
    1766, 1791, 1817, 1844, 1871, 1900, 1929, 1958, 1990, 2021, 2054, 2088, 2123, 2159, 2197, 2236, 2276, 2319, 2363,
    2410, 2458, 2508, 2561, 2616, 2675, 2737, 2802, 2871, 2944, 3020, 3102, 3188, 3280, 3375, 3478, 3586, 3702, 3823,
    3953, 4089, 4236, 4394, 4559, 4737, 4929, 5130, 5347
])
dc_X = np.arange(dc.shape[0])


if metric_has_metric:
    def probing_perform_probing(probing_tmp_dir, probing_scenes_file, probing_output_file, probing_output_file_lwi):
        probing_output_file.unlink(missing_ok=True)
        probing_output_file_lwi.unlink(missing_ok=True)

        command = [
            "av1an",
            "-y"]
        if verbose >= 2:
            command += ["--verbose"]
        command += [
            "--temp", probing_tmp_dir,
            "--keep"
        ]
        if resume:
            command += ["--resume"]
        command += [
            "-i", probing_input_file
        ]
        if probing_input_vspipe_args is not None:
            command += ["--vspipe-args"] + probing_input_vspipe_args
        command += [
            "-o", probing_output_file,
            "--scenes", probing_scenes_file,
            *zone_default.probing_av1an_parameters(f"[K[0m[1;3m> Progression Boost [0m[3m{probing_output_file.stem}[0m[1;3m <[0m")
        ]
        return subprocess.Popen(command, text=True)
    
    probing_first_tmp_dir = progression_boost_temp_dir / f"probe-encode-first.tmp"
    probing_first_scenes_file = progression_boost_temp_dir / f"probe-encode-first.scenes.json"
    probing_first_output_file = progression_boost_temp_dir / f"probe-encode-first.mkv"
    probing_first_output_file_lwi = progression_boost_temp_dir / f"probe-encode-first.lwi"
    
    probing_second_tmp_dir = progression_boost_temp_dir / f"probe-encode-second.tmp"
    probing_second_scenes_file = progression_boost_temp_dir / f"probe-encode-second.scenes.json"
    probing_second_output_file = progression_boost_temp_dir / f"probe-encode-second.mkv"
    probing_second_output_file_lwi = progression_boost_temp_dir / f"probe-encode-second.lwi"

    metric_result_file = progression_boost_temp_dir / f"result.json"

    probing_first_perform_encode = False
    probing_second_perform_encode = False

    if resume and metric_result_file.exists():
        with metric_result_file.open("r") as result_f:
            metric_result = json.load(result_f)
    else:
        metric_result = copy.deepcopy(scenes)

    if not resume or not probing_first_output_file.exists():
        probing_first_perform_encode = True

    if probing_first_perform_encode:
        for scene_n, zone_scene in enumerate(zone_scenes["scenes"]):
            if zone_scene["zone"].metric_enable:
                if "first_score" in metric_result["scenes"][scene_n]:
                    del metric_result["scenes"][scene_n]["first_score"]

    for scene_n, zone_scene in enumerate(zone_scenes["scenes"]):
        if zone_scene["zone"].metric_enable:
            if "first_score" not in metric_result["scenes"][scene_n]:
                probing_second_perform_encode = True
                shutil.rmtree(probing_second_tmp_dir, ignore_errors=True)
                break

    if not resume or not probing_second_output_file.exists():
        probing_second_perform_encode = True

    if probing_second_perform_encode:
        for scene_n, zone_scene in enumerate(zone_scenes["scenes"]):
            if zone_scene["zone"].metric_enable:
                if "second_score" in metric_result["scenes"][scene_n]:
                    del metric_result["scenes"][scene_n]["second_score"]

    with metric_result_file.open("w") as metric_result_f:
        json.dump(metric_result, metric_result_f, cls=NumpyEncoder)

if metric_has_metric and probing_first_perform_encode:
    probing_first_scenes = {}
    probing_first_scenes["scenes"] = []
    total_frames = 0
    for scene_n, zone_scene in enumerate(zone_scenes["scenes"]):
        if zone_scene["zone"].metric_enable:
            metric_result["scenes"][scene_n]["first_qstep"] = 343

            total_frames += zone_scene["end_frame"] - zone_scene["start_frame"]
            probing_scene = {
                "start_frame": zone_scene["start_frame"],
                "end_frame": zone_scene["end_frame"],
                "zone_overrides": copy.copy(zone_scene["zone_overrides"])
            }
            if zone_scene["zone"].quarterstep_crf:
                probing_scene["zone_overrides"]["video_params"] = [
                    "--crf", f"{(np.searchsorted(dc, metric_result["scenes"][scene_n]["first_qstep"], side="right") - 1) / 4:.2f}"
                ]
            else:
                probing_scene["zone_overrides"]["video_params"] = [
                    "--crf", f"{(np.searchsorted(dc, metric_result["scenes"][scene_n]["first_qstep"], side="right") - 1) / 4:.0f}"
                ]
            probing_scene["zone_overrides"]["video_params"] += [
                "--preset", f"{zone_scene["zone"].probing_preset}",
                *zone_scene["zone"].probing_dynamic_parameters(crf=(np.searchsorted(dc, metric_result["scenes"][scene_n]["first_qstep"], side="right") - 1) / 4)
            ]
            probing_scene["zone_overrides"]["photon_noise"] = None
            probing_scene["zone_overrides"]["photon_noise_height"] = None
            probing_scene["zone_overrides"]["photon_noise_width"] = None
            probing_scene["zone_overrides"]["chroma_noise"] = False
            probing_first_scenes["scenes"].append(probing_scene)
    probing_first_scenes["frames"] = total_frames
    probing_first_scenes["split_scenes"] = probing_first_scenes["scenes"]
            
    with probing_first_scenes_file.open("w") as probing_scenes_f:
        json.dump(probing_first_scenes, probing_scenes_f, cls=NumpyEncoder)

    probing_first_process = probing_perform_probing(probing_first_tmp_dir, probing_first_scenes_file, probing_first_output_file, probing_first_output_file_lwi)
    

if not scene_detection_diffs_available:
    scene_detection_measure_frame_luma()


if character_has_character:
    character_file = character_boost_temp_dir / "kyara.json"

    if resume and character_file.exists():
        with character_file.open("r") as character_f:
            character_kyara = json.load(character_f)
    else:
        character_kyara = copy.deepcopy(scenes)

    import vsmlrt

    character_clip = zone_default.source_clip

    character_block_width = math.ceil(character_clip.width / 64)
    character_block_height = math.ceil(character_clip.height / 64)
    character_clip = character_clip.resize.Bicubic(filter_param_a=0, filter_param_b=0.5, \
                                                   width=character_block_width*64, height=character_block_height*64, src_width=character_block_width*64, src_height=character_block_height*64, \
                                                   format=vs.RGBS, primaries_in=1, matrix_in=1, transfer_in=1, range_in=0, transfer=13, range=1)
    character_clip = vsmlrt.inference(character_clip, character_model, backend=character_backend)
    character_clip = character_clip.akarin.Expr("x 0.95 > x 0 ?")

    character_clip = character_clip.std.PlaneStats(prop="Kyara")

    character_clip = character_clip.resize.Bicubic(filter_param_a=0, filter_param_b=0, \
                                                   width=character_block_width, height=character_block_height)
    character_clip = character_clip.akarin.Expr("x 2 *")
    character_clip = character_clip.akarin.Expr("""
x[-1,-1] x[-1,0] x[-1,1] x[0,-1] x[0,0] x[0,1] x[1,-1] x[1,0] x[1,1] + + + + + + + + 9 / avg!
avg@ x > avg@ x ? r!
r@ 1 < r@ 1 ? r!
r@ -1 > r@ -1 ?""")

    def character_calculate_character(character_map_file, scene_n):
        diffs = scene_detection_diffs[scenes["scenes"][scene_n]["start_frame"]:scenes["scenes"][scene_n]["end_frame"]]
        frames = np.zeros((math.ceil(diffs.shape[0] / 32) * 32 + 1,), dtype=bool)

        frames[0] = True
        for frame, diff in enumerate(diffs):
            if diff >= 0.0012:
                frames[[math.floor(frame / 4) * 4, math.ceil(frame / 4) * 4]] = True
                frames[[math.floor(frame / 8) * 8, math.ceil(frame / 8) * 8]] = True
                frames[[math.floor(frame / 16) * 16, math.ceil(frame / 16) * 16]] = True
                frames[[math.floor(frame / 32) * 32, math.ceil(frame / 32) * 32]] = True

        character_map = np.full(((scenes["scenes"][scene_n]["end_frame"] - scenes["scenes"][scene_n]["start_frame"]) // 4, character_block_width * character_block_height),
                                np.nan, dtype=np.float64)

        clip = character_clip[int(scenes["scenes"][scene_n]["start_frame"])]
        clip_map = [0]
        for i in range(1, character_map.shape[0]):
            if frames[i * 4]:
                clip += character_clip[int(scenes["scenes"][scene_n]["start_frame"] + i * 4)]
                clip_map.append(i)

        character_kyara["scenes"][scene_n]["kyara"] = 0.0
        for i, frame in enumerate(clip.frames(backlog=48)):
            character_map[clip_map[i]] = np.array(frame[0], dtype=np.float32).reshape((-1,))
            character_kyara["scenes"][scene_n]["kyara"] = np.max([frame.props["KyaraAverage"], character_kyara["scenes"][scene_n]["kyara"]])

        np.save(character_map_file, character_map)
        with character_file.open("w") as character_f:
            json.dump(character_kyara, character_f, cls=NumpyEncoder)

    character_precalc = 0

if metric_has_metric and probing_first_perform_encode and character_has_character:
    start = time() - 0.000001
    start_count = -1
    for scene_n in range(0, len(scenes["scenes"])):
        if zone_scenes["scenes"][scene_n]["zone"].character_enable:
            character_precalc = scene_n

            if probing_first_process.poll() is not None:
                print(f"\r\033[K{scene_frame_print(scene_n)} / Character segmentation paused / {start_count / (time() - start):.2f} scenes per second", end="\n")
                break

            character_map_file = character_boost_temp_dir / f"character-{scene_rjust(scene_n)}.npy"
            if not resume or not character_map_file.exists() or "kyara" not in character_kyara["scenes"][scene_n]:
                start_count += 1
                print(f"\r\033[K{scene_frame_print(scene_n)} / Performing character segmentation / {start_count / (time() - start):.2f} scenes per second", end="")

                character_calculate_character(character_map_file, scene_n)
    else:
        character_precalc = len(scenes["scenes"])
        if start_count != -1:
            print(f"\r\033[K{scene_frame_print(scene_n)} / Character segmentation complete / {(start_count + 1) / (time() - start):.2f} scenes per second", end="\n")


if metric_has_metric and probing_first_perform_encode:
    probing_first_process.wait()
    assert probing_first_output_file.exists()


if metric_has_metric:
    for zone in zones:
        if zone_scene["zone"].metric_enable and zone["zone"].metric_method == "vapoursynth":
            metric_method_has_vapoursynth = True
            break
    else:
        metric_method_has_vapoursynth = False
    for zone in zones:
        if zone_scene["zone"].metric_enable and zone["zone"].metric_method == "ffvship":
            metric_method_has_ffvship = True
            break
    else:
        metric_method_has_ffvship = False

    metric_processed_reference = {}
    metric_first = core.lsmas.LWLibavSource(probing_first_output_file.expanduser().resolve(),
                                            cachefile=probing_first_output_file_lwi.expanduser().resolve())
    metric_processed_first = {}

    metric_diff_clips = {}
    if metric_method_has_vapoursynth:
        metric_first_metric_clips = {}

    if metric_method_has_ffvship:
        metric_ffvship_output_file = progression_boost_temp_dir / "metric-ffvship.json"

    start = time() - 0.000001
    start_count = -1
    probing_frame_head = 0
    for scene_n, zone_scene in enumerate(zone_scenes["scenes"]):
        if zone_scene["zone"].metric_enable:
            if "first_score" not in metric_result["scenes"][scene_n]:
                start_count += 1
                print(f"\r\033[K{scene_frame_print(scene_n)} / Calculating metric / {start_count / (time() - start):.2f} scenes per second", end="")
    
                assert zone_scene["zone"].metric_method in ["ffvship", "vapoursynth"], "Invalid `metric_method`. Please check your config inside `Progression-Boost.py`."

            if zone_scene["zone"] not in metric_processed_reference:
                metric_processed_reference[zone_scene["zone"]] = zone_scene["zone"].metric_process(zone_scene["zone"].metric_reference)
            if zone_scene["zone"] not in metric_processed_first:
                metric_processed_first[zone_scene["zone"]] = zone_scene["zone"].metric_process(metric_first)
                
            reference_offset = zone_scene["start_frame"] - probing_frame_head


            if "frames" not in metric_result["scenes"][scene_n]:
                if verbose >= 2:
                    print(f"\r\033[K{scene_frame_print(scene_n)} / Frame selection", end="", flush=True)

                rng = default_rng(1188246) # Guess what is this number. It's the easiest cipher out there.
            
                # These frames are offset from `scene["start_frame"] + 1` and that's why they are offfset, not offset
                offfset_frames = np.array([], dtype=np.int32)
                
                scene_diffs = scene_detection_diffs[zone_scene["start_frame"] + 1:zone_scene["end_frame"]]

                transform = fftpack.dct(scene_diffs)
                transform[np.max([math.ceil(transform.shape[0] / 5), 7]):] = 0
                reconstructed = fftpack.idct(transform)

                peaks, properties = signal.find_peaks(reconstructed, prominence=0)
                peaks_sort = peaks[np.argsort(properties["prominences"])[::-1]]

                picked = 0
                if verbose >= 2:
                    print(f" / peak transformed", end="", flush=True)
                for offfset_frame in peaks_sort:
                    if picked >= zone_scene["zone"].metric_peak_transformed_diff_frames:
                        break
                    offfset_frames = np.append(offfset_frames, offfset_frame)
                    picked += 1
                    if verbose >= 2:
                        print(f" {zone_scene["start_frame"] + 1 + offfset_frame}", end="", flush=True)

                scene_diffs_sort = np.argsort(scene_diffs)[::-1]

                picked = 0
                if verbose >= 2:
                    print(f" / highest diff", end="", flush=True)
                for offfset_frame in scene_diffs_sort:
                    if picked >= zone_scene["zone"].metric_highest_diff_frames:
                        break
                    if offfset_frame in offfset_frames:
                        continue
                    offfset_frames = np.append(offfset_frames, offfset_frame)
                    picked += 1
                    if verbose >= 2:
                        print(f" {zone_scene["start_frame"] + 1 + offfset_frame}", end="", flush=True)

                if zone_scene["zone"].metric_highest_probing_diff_frames:
                    if (zone_scene["zone"], reference_offset) not in metric_diff_clips:
                        metric_diff_clips[(zone_scene["zone"], reference_offset)] = core.std.PlaneStats(metric_processed_reference[zone_scene["zone"]][reference_offset:],
                                                                                                        metric_processed_first[zone_scene["zone"]],
                                                                                                        prop="Encode")
                    clip = metric_diff_clips[(zone_scene["zone"], reference_offset)][probing_frame_head:probing_frame_head + zone_scene["end_frame"] - zone_scene["start_frame"]]
                    encode_diffs = [frame.props["EncodeDiff"] for frame in clip.frames(backlog=48)]
                    encode_diffs_sort = np.argsort(encode_diffs, stable=True)[::-1]
                    picked = 0
                    if verbose >= 2:
                        print(f" / highest probing diff", end="", flush=True)
                    for frame in encode_diffs_sort:
                        if picked >= zone_scene["zone"].metric_highest_probing_diff_frames:
                            break
                        if frame - 1 in offfset_frames:
                            continue
                        offfset_frames = np.append(offfset_frames, frame - 1)
                        picked += 1
                        if verbose >= 2:
                            print(f" {zone_scene["start_frame"] + frame}", end="", flush=True)
                
                if zone_scene["zone"].metric_last_frame >= 1 and zone_scene["end_frame"] - zone_scene["start_frame"] - 2 not in offfset_frames:
                    offfset_frames = np.append(offfset_frames, zone_scene["end_frame"] - zone_scene["start_frame"] - 2)
                    if verbose >= 2:
                        print(f" / last {zone_scene["end_frame"] - 1}", end="", flush=True)
            
                scene_diffs_percentile = np.percentile(scene_diffs, 40, method="linear")
                scene_diffs_percentile_absolute_deviation = np.percentile(np.abs(scene_diffs - scene_diffs_percentile), 40, method="linear")
                scene_diffs_upper_bracket_ = np.argwhere(scene_diffs > scene_diffs_percentile + 5 * scene_diffs_percentile_absolute_deviation).reshape((-1))
                scene_diffs_lower_bracket_ = np.argwhere(scene_diffs <= scene_diffs_percentile + 5 * scene_diffs_percentile_absolute_deviation).reshape((-1))
                scene_diffs_upper_bracket = np.empty_like(scene_diffs_upper_bracket_)
                rng.shuffle((scene_diffs_upper_bracket__ := scene_diffs_upper_bracket_[:math.ceil(scene_diffs_upper_bracket_.shape[0] / 2)]))
                scene_diffs_upper_bracket[::2] = scene_diffs_upper_bracket__
                rng.shuffle((scene_diffs_upper_bracket__ := scene_diffs_upper_bracket_[-math.floor(scene_diffs_upper_bracket_.shape[0] / 2):]))
                scene_diffs_upper_bracket[1::2] = scene_diffs_upper_bracket__
                scene_diffs_lower_bracket = np.empty_like(scene_diffs_lower_bracket_)
                rng.shuffle((scene_diffs_lower_bracket__ := scene_diffs_lower_bracket_[:math.ceil(scene_diffs_lower_bracket_.shape[0] / 2)]))
                scene_diffs_lower_bracket[::2] = scene_diffs_lower_bracket__
                rng.shuffle((scene_diffs_lower_bracket__ := scene_diffs_lower_bracket_[-math.floor(scene_diffs_lower_bracket_.shape[0] / 2):]))
                scene_diffs_lower_bracket[1::2] = scene_diffs_lower_bracket__
            
                picked = 0
                if verbose >= 2:
                    print(f" / upper bracket", end="", flush=True)
                for offfset_frame in scene_diffs_upper_bracket:
                    if picked >= zone_scene["zone"].metric_upper_diff_bracket_frames:
                        break
                    if offfset_frames.shape[0] != 0 and np.min(np.abs(offfset_frames - offfset_frame)) < zone_scene["zone"].metric_diff_brackets_min_separation:
                        continue
                    offfset_frames = np.append(offfset_frames, offfset_frame)
                    picked += 1
                    if verbose >= 2:
                        print(f" {zone_scene["start_frame"] + 1 + offfset_frame}", end="", flush=True)
                
                if picked < zone_scene["zone"].metric_upper_diff_bracket_fallback_frames:
                    to_pick = zone_scene["zone"].metric_lower_diff_bracket_frames + zone_scene["zone"].metric_upper_diff_bracket_fallback_frames - picked
                else:
                    to_pick = zone_scene["zone"].metric_lower_diff_bracket_frames
            
                if zone_scene["zone"].metric_first_frame >= 1:
                    offfset_frames = np.append(offfset_frames, -1)
                    if verbose >= 2:
                        print(f" / first {zone_scene["start_frame"]}", end="", flush=True)
            
                picked = 0
                if verbose >= 2:
                    print(f" / lower bracket", end="", flush=True)
                for offfset_frame in scene_diffs_lower_bracket:
                    if picked >= to_pick:
                        break
                    if offfset_frames.shape[0] != 0 and np.min(np.abs(offfset_frames - offfset_frame)) < zone_scene["zone"].metric_diff_brackets_min_separation:
                        continue
                    offfset_frames = np.append(offfset_frames, offfset_frame)
                    picked += 1
                    if verbose >= 2:
                        print(f" {zone_scene["start_frame"] + 1 + offfset_frame}", end="", flush=True)

                if verbose >= 2:
                    print(f"", end="\n", flush=True)
                    
                metric_result["scenes"][scene_n]["frames"] = np.sort(offfset_frames) + 1


            if "first_score" not in metric_result["scenes"][scene_n]:
                if zone_scene["zone"].metric_method == "vapoursynth":
                    if (zone_scene["zone"], reference_offset) not in metric_first_metric_clips:
                        metric_first_metric_clips[(zone_scene["zone"], reference_offset)] = zone_scene["zone"].metric_vapoursynth_calculate(metric_processed_reference[zone_scene["zone"]][reference_offset:], metric_processed_first[zone_scene["zone"]])
        
                    clip = metric_first_metric_clips[(zone_scene["zone"], reference_offset)][int(metric_result["scenes"][scene_n]["frames"][0] + probing_frame_head)]
                    for frame in metric_result["scenes"][scene_n]["frames"][1:]:
                        clip += metric_first_metric_clips[(zone_scene["zone"], reference_offset)][int(frame + probing_frame_head)]
        
                    scores = np.array([zone_scene["zone"].metric_vapoursynth_metric(frame) for frame in clip.frames(backlog=48)])
                    
                elif zone_scene["zone"].metric_method == "ffvship":
                    metric_ffvship_output_file.unlink(missing_ok=True)

                    command = [
                        "FFVship",
                        "--source", input_file,
                        "--encoded", probing_first_output_file,
                        "--metric", zone_scene["zone"].metric_ffvship_calculate
                    ]
                    if zone_scene["zone"].metric_ffvship_calculate == "Butteraugli" and zone_scene["zone"].metric_ffvship_intensity_target is not None:
                        command += ["--intensity-target", str(zone_scene["zone"].metric_ffvship_intensity_target)]
                    command += [
                        "--json", metric_ffvship_output_file,
                        "--source-indices", ",".join([str(frame) for frame in (metric_result["scenes"][scene_n]["frames"] + zone_scene["start_frame"])]),
                        "--encoded-offset", str(-reference_offset),
                        *zone_scene["zone"].metric_ffvship_extra_parameters
                    ]
                    subprocess.run(command, text=True, stdout=subprocess.DEVNULL)
                    assert metric_ffvship_output_file.exists()

                    with metric_ffvship_output_file.open("r") as metric_output_f:
                        scores = json.load(metric_output_f)
                    scores = np.array([zone_scene["zone"].metric_ffvship_metric(frame) for frame in scores])
                
                metric_result["scenes"][scene_n]["first_score"] = zone_scene["zone"].metric_summarise(scores)


            probing_frame_head += zone_scene["end_frame"] - zone_scene["start_frame"]

            with metric_result_file.open("w") as metric_result_f:
                json.dump(metric_result, metric_result_f, cls=NumpyEncoder)

    if start_count != -1:
        print(f"\r\033[K{scene_frame_print(scene_n)} / Metric calculation complete / {(start_count + 1) / (time() - start):.2f} scenes per second", end="\n")


#  ██████╗ ██████╗  ██████╗ ██████╗ ██╗███╗   ██╗ ██████╗       ███████╗███████╗ ██████╗ ██████╗ ███╗   ██╗██████╗ 
#  ██╔══██╗██╔══██╗██╔═══██╗██╔══██╗██║████╗  ██║██╔════╝       ██╔════╝██╔════╝██╔════╝██╔═══██╗████╗  ██║██╔══██╗
#  ██████╔╝██████╔╝██║   ██║██████╔╝██║██╔██╗ ██║██║  ███╗█████╗███████╗█████╗  ██║     ██║   ██║██╔██╗ ██║██║  ██║
#  ██╔═══╝ ██╔══██╗██║   ██║██╔══██╗██║██║╚██╗██║██║   ██║╚════╝╚════██║██╔══╝  ██║     ██║   ██║██║╚██╗██║██║  ██║
#  ██║     ██║  ██║╚██████╔╝██████╔╝██║██║ ╚████║╚██████╔╝      ███████║███████╗╚██████╗╚██████╔╝██║ ╚████║██████╔╝
#  ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝       ╚══════╝╚══════╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚═════╝ 


if metric_has_metric and probing_second_perform_encode:
    probing_second_scenes = {}
    probing_second_scenes["scenes"] = []
    total_frames = 0
    for scene_n, zone_scene in enumerate(zone_scenes["scenes"]):
        if zone_scene["zone"].metric_enable:
            if zone_scene["zone"].metric_better(metric_result["scenes"][scene_n]["first_score"], zone_scene["zone"].metric_target):
                metric_result["scenes"][scene_n]["second_qstep"] = 891
            else:
                metric_result["scenes"][scene_n]["second_qstep"] = 155

            total_frames += zone_scene["end_frame"] - zone_scene["start_frame"]
            probing_scene = {
                "start_frame": zone_scene["start_frame"],
                "end_frame": zone_scene["end_frame"],
                "zone_overrides": copy.copy(zone_scene["zone_overrides"])
            }
            if zone_scene["zone"].quarterstep_crf:
                probing_scene["zone_overrides"]["video_params"] = [
                    "--crf", f"{(np.searchsorted(dc, metric_result["scenes"][scene_n]["second_qstep"], side="right") - 1) / 4:.2f}"
                ]
            else:
                probing_scene["zone_overrides"]["video_params"] = [
                    "--crf", f"{(np.searchsorted(dc, metric_result["scenes"][scene_n]["second_qstep"], side="right") - 1) / 4:.0f}"
                ]
            probing_scene["zone_overrides"]["video_params"] += [
                "--preset", f"{zone_scene["zone"].probing_preset}",
                *zone_scene["zone"].probing_dynamic_parameters(crf=(np.searchsorted(dc, metric_result["scenes"][scene_n]["second_qstep"], side="right") - 1) / 4)
            ]
            probing_scene["zone_overrides"]["photon_noise"] = None
            probing_scene["zone_overrides"]["photon_noise_height"] = None
            probing_scene["zone_overrides"]["photon_noise_width"] = None
            probing_scene["zone_overrides"]["chroma_noise"] = False
            probing_second_scenes["scenes"].append(probing_scene)
    probing_second_scenes["frames"] = total_frames
    probing_second_scenes["split_scenes"] = probing_second_scenes["scenes"]
            
    with probing_second_scenes_file.open("w") as probing_scenes_f:
        json.dump(probing_second_scenes, probing_scenes_f, cls=NumpyEncoder)

    probing_second_process = probing_perform_probing(probing_second_tmp_dir, probing_second_scenes_file, probing_second_output_file, probing_second_output_file_lwi)


if character_has_character:
    start = time() - 0.000001
    start_count = -1
    for scene_n in range(character_precalc, len(scenes["scenes"])):
        if zone_scenes["scenes"][scene_n]["zone"].character_enable:
            character_map_file = character_boost_temp_dir / f"character-{scene_rjust(scene_n)}.npy"
            if not resume or not character_map_file.exists() or "kyara" not in character_kyara["scenes"][scene_n]:
                start_count += 1
                print(f"\r\033[K{scene_frame_print(scene_n)} / Performing character segmentation / {start_count / (time() - start):.2f} scenes per second", end="")

                character_calculate_character(character_map_file, scene_n)
    else:
        if start_count != -1:
            if character_precalc == 0:
                print(f"\r\033[K{scene_frame_print(scene_n)} / Character segmentation complete / {(start_count + 1) / (time() - start):.2f} scenes per second", end="\n")
            elif character_precalc != len(scenes["scenes"]):
                print(f"\r\033[K{scene_frame_print(scene_n)} / Character segmentation complete", end="\n")


if metric_has_metric and probing_second_perform_encode:
    probing_second_process.wait()
    assert probing_second_output_file.exists()

if metric_has_metric:
    if metric_method_has_vapoursynth:
        metric_processed_reference = {}
        
        metric_second = core.lsmas.LWLibavSource(probing_second_output_file.expanduser().resolve(),
                                                 cachefile=probing_second_output_file_lwi.expanduser().resolve())
        metric_processed_second = {}
        metric_second_metric_clips = {}

    start = time() - 0.000001
    start_count = -1
    probing_frame_head = 0
    for scene_n, zone_scene in enumerate(zone_scenes["scenes"]):
        if zone_scene["zone"].metric_enable:
            if "second_score" not in metric_result["scenes"][scene_n]:
                start_count += 1
                print(f"\r\033[K{scene_frame_print(scene_n)} / Calculating metric / {start_count / (time() - start):.2f} scenes per second", end="")

                assert "frames" in metric_result["scenes"][scene_n], "This indicates a bug in the original code. Please report this to the repository including this entire error message."
    
                reference_offset = zone_scene["start_frame"] - probing_frame_head
                if zone_scene["zone"].metric_method == "vapoursynth":
                    if zone_scene["zone"] not in metric_processed_reference:
                        metric_processed_reference[zone_scene["zone"]] = zone_scene["zone"].metric_process(zone_scene["zone"].metric_reference)
                    if zone_scene["zone"] not in metric_processed_second:
                        metric_processed_second[zone_scene["zone"]] = zone_scene["zone"].metric_process(metric_second)
    
                    if (zone_scene["zone"], reference_offset) not in metric_second_metric_clips:
                        metric_second_metric_clips[(zone_scene["zone"], reference_offset)] = zone_scene["zone"].metric_vapoursynth_calculate(metric_processed_reference[zone_scene["zone"]][reference_offset:], metric_processed_second[zone_scene["zone"]])
        
                    clip = metric_second_metric_clips[(zone_scene["zone"], reference_offset)][int(metric_result["scenes"][scene_n]["frames"][0] + probing_frame_head)]
                    for frame in metric_result["scenes"][scene_n]["frames"][1:]:
                        clip += metric_second_metric_clips[(zone_scene["zone"], reference_offset)][int(frame + probing_frame_head)]
        
                    scores = np.array([zone_scene["zone"].metric_vapoursynth_metric(frame) for frame in clip.frames(backlog=48)])
                    
                elif zone_scene["zone"].metric_method == "ffvship":
                    metric_ffvship_output_file.unlink(missing_ok=True)

                    command = [
                        "FFVship",
                        "--source", input_file,
                        "--encoded", probing_second_output_file,
                        "--metric", zone_scene["zone"].metric_ffvship_calculate
                    ]
                    if zone_scene["zone"].metric_ffvship_calculate == "Butteraugli" and zone_scene["zone"].metric_ffvship_intensity_target is not None:
                        command += ["--intensity-target", str(zone_scene["zone"].metric_ffvship_intensity_target)]
                    command += [
                        "--json", metric_ffvship_output_file,
                        "--source-indices", ",".join([str(frame) for frame in (metric_result["scenes"][scene_n]["frames"] + zone_scene["start_frame"])]),
                        "--encoded-offset", str(-reference_offset),
                        *zone_scene["zone"].metric_ffvship_extra_parameters
                    ]
                    subprocess.run(command, text=True, stdout=subprocess.DEVNULL)
                    assert metric_ffvship_output_file.exists()

                    with metric_ffvship_output_file.open("r") as metric_output_f:
                        scores = json.load(metric_output_f)
                    scores = np.array([zone_scene["zone"].metric_ffvship_metric(frame) for frame in scores])
                
                metric_result["scenes"][scene_n]["second_score"] = zone_scene["zone"].metric_summarise(scores)

            probing_frame_head += zone_scene["end_frame"] - zone_scene["start_frame"]

            with metric_result_file.open("w") as metric_result_f:
                json.dump(metric_result, metric_result_f, cls=NumpyEncoder)

    if start_count != -1:
        print(f"\r\033[K{scene_frame_print(scene_n)} / Metric calculation complete / {(start_count + 1) / (time() - start):.2f} scenes per second", end="\n")

    # Failsafe for `--resume`
    for scene_n, zone_scene in enumerate(zone_scenes["scenes"]):
        if zone_scene["zone"].metric_enable:
            if "first_qstep" not in metric_result["scenes"][scene_n]:
                metric_result["scenes"][scene_n]["first_qstep"] = 343

    if verbose >= 2:
        for scene_n, zone_scene in enumerate(zone_scenes["scenes"]):
            if zone_scene["zone"].metric_enable:
                print(f"\r\033[K{scene_frame_print(scene_n)} / Metric result / first_qstep {metric_result["scenes"][scene_n]["first_qstep"]} / first_score {metric_result["scenes"][scene_n]["first_score"]:.3f} / second_qstep {metric_result["scenes"][scene_n]["second_qstep"]} / second_score {metric_result["scenes"][scene_n]["second_score"]:.3f}", end="\n")


#  ███████╗██╗███╗   ██╗ █████╗ ██╗     
#  ██╔════╝██║████╗  ██║██╔══██╗██║     
#  █████╗  ██║██╔██╗ ██║███████║██║     
#  ██╔══╝  ██║██║╚██╗██║██╔══██║██║     
#  ██║     ██║██║ ╚████║██║  ██║███████╗
#  ╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝


final_scenes = copy.deepcopy(scenes)
final_crf_frames = np.zeros((10,), dtype=np.int32)
start = time() - 0.000001
for scene_n, zone_scene in enumerate(zone_scenes["scenes"]):
    if verbose < 1:
        print(f"\r\033[K{scene_frame_print(scene_n)} / Calculating boost / {scene_n / (time() - start):.0f} scenes per second", end="")
    if verbose >= 1:
        print(f"\r\033[K{scene_frame_print(scene_n)} / Calculating boost / --crf / ", end="", flush=True)

    if zone_scene["zone"].metric_enable:
        assert "first_qstep" in metric_result["scenes"][scene_n], "This indicates a bug in the original code. Please report this to the repository including this entire error message."
        assert "first_score" in metric_result["scenes"][scene_n], "This indicates a bug in the original code. Please report this to the repository including this entire error message."
        assert "second_qstep" in metric_result["scenes"][scene_n], "This indicates a bug in the original code. Please report this to the repository including this entire error message."
        assert "second_score" in metric_result["scenes"][scene_n], "This indicates a bug in the original code. Please report this to the repository including this entire error message."

        if verbose >= 1:
            print(f"Progression Boost ", end="", flush=True)

        def metric_linear(readjusting):
            fit = Polynomial.fit([metric_result["scenes"][scene_n]["first_score"], metric_result["scenes"][scene_n]["second_score"]],
                                 [metric_result["scenes"][scene_n]["first_qstep"], metric_result["scenes"][scene_n]["second_qstep"]],
                                 1)
            qstep = fit(zone_scene["zone"].metric_target)

            crf = np.interp(qstep, dc, dc_X) / 4
            crf = np.clip(crf, zone_scene["zone"].metric_min_crf, zone_scene["zone"].metric_max_crf)
            preset = zone_scene["zone"].metric_dynamic_preset(crf)
            if verbose >= 1:
                print(f"original {crf:>5.2f} / ", end="", flush=True)

            if readjusting:
                readjusted_second_score = metric_result["scenes"][scene_n]["second_score"]
                if zone_scene["zone"].probing_preset >= 6:
                    if preset <= -1:
                        readjusted_second_score -= (metric_result["scenes"][scene_n]["first_score"] - metric_result["scenes"][scene_n]["second_score"]) * 0.63
                    elif preset <= 0:
                        readjusted_second_score -= (metric_result["scenes"][scene_n]["first_score"] - metric_result["scenes"][scene_n]["second_score"]) * 0.60
                    elif preset <= 2:
                        readjusted_second_score -= (metric_result["scenes"][scene_n]["first_score"] - metric_result["scenes"][scene_n]["second_score"]) * 0.51
                    elif preset <= 5:
                        readjusted_second_score -= (metric_result["scenes"][scene_n]["first_score"] - metric_result["scenes"][scene_n]["second_score"]) * 0.30
                elif zone_scene["zone"].probing_preset >= 5:
                    if preset <= -1:
                        readjusted_second_score -= (metric_result["scenes"][scene_n]["first_score"] - metric_result["scenes"][scene_n]["second_score"]) * 0.33
                    elif preset <= 0:
                        readjusted_second_score -= (metric_result["scenes"][scene_n]["first_score"] - metric_result["scenes"][scene_n]["second_score"]) * 0.30
                    elif preset <= 2:
                        readjusted_second_score -= (metric_result["scenes"][scene_n]["first_score"] - metric_result["scenes"][scene_n]["second_score"]) * 0.21
                elif zone_scene["zone"].probing_preset >= 3:
                    if preset <= 0:
                        readjusted_second_score -= (metric_result["scenes"][scene_n]["first_score"] - metric_result["scenes"][scene_n]["second_score"]) * 0.15
                    elif preset <= 2:
                        readjusted_second_score -= (metric_result["scenes"][scene_n]["first_score"] - metric_result["scenes"][scene_n]["second_score"]) * 0.12

                fit = Polynomial.fit([metric_result["scenes"][scene_n]["first_score"], readjusted_second_score],
                                     [metric_result["scenes"][scene_n]["first_qstep"], metric_result["scenes"][scene_n]["second_qstep"]],
                                     1)
                qstep = fit(zone_scene["zone"].metric_target)

                crf = np.interp(qstep, dc, dc_X) / 4
                crf = np.clip(crf, zone_scene["zone"].metric_min_crf, zone_scene["zone"].metric_max_crf)

            if verbose >= 1:
                print(f"readjusted {crf:>5.2f} / ", end="", flush=True)

            return crf, preset

        if metric_result["scenes"][scene_n]["first_qstep"] < metric_result["scenes"][scene_n]["second_qstep"]:
            if zone_scene["zone"].metric_better(metric_result["scenes"][scene_n]["first_score"], metric_result["scenes"][scene_n]["second_score"]):
                crf, preset = metric_linear(readjusting=True)
            else:
                crf = np.interp(np.mean([metric_result["scenes"][scene_n]["first_qstep"], metric_result["scenes"][scene_n]["second_qstep"]]), dc, dc_X) / 4
                crf = np.clip(crf, zone_scene["zone"].metric_min_crf, zone_scene["zone"].metric_max_crf)
                preset = zone_scene["zone"].metric_dynamic_preset(crf)
                if verbose >= 1:
                    print(f"fallback {crf:>5.2f} / ", end="", flush=True)
        else: # second_qstep < first_qstep
            if zone_scene["zone"].metric_better(metric_result["scenes"][scene_n]["second_score"], metric_result["scenes"][scene_n]["first_score"]):
                crf, preset = metric_linear(readjusting=False)
            else:
                crf = np.min([zone_scene["zone"].metric_unreliable_crf_fallback(), (np.searchsorted(dc, metric_result["scenes"][scene_n]["second_qstep"], side="right") - 1) / 4])
                crf = np.clip(crf, zone_scene["zone"].metric_min_crf, zone_scene["zone"].metric_max_crf)
                preset = zone_scene["zone"].metric_dynamic_preset(crf)
                if verbose >= 1:
                    print(f"fallback {crf:>5.2f} / ", end="", flush=True)
        crf = zone_scene["zone"].metric_dynamic_crf(crf)
    else:
        crf = zone_scene["zone"].metric_disabled_crf
        crf = np.clip(crf, zone_scene["zone"].metric_min_crf, zone_scene["zone"].metric_max_crf)
        preset = zone_scene["zone"].metric_dynamic_preset(crf)
        if verbose >= 1:
            print(f"Starting {crf:>5.2f} / ", end="", flush=True)

    if zone_scene["zone"].character_enable:
        if verbose >= 1:
            print(f"Character Boost ", end="", flush=True)

        character_map_file = character_boost_temp_dir / f"character-{scene_rjust(scene_n)}.npy"

        assert character_map_file.exists(), "This indicates a bug in the original code. Please report this to the repository including this entire error message."

        character_map = np.load(character_map_file)

        if zone["zone"].character_max_roi_boost:
            roi_map = []
    
            uniform_offset = zone_scene["zone"].character_max_roi_boost // 2.0
            uniform_nonboosting_offset = zone_scene["zone"].character_max_roi_boost // 1.2
            uniform_ending_nonboosting_offset = zone_scene["zone"].character_max_roi_boost // 4.8
            character_key_multiplier = 1.00
            character_32_multiplier = 0.90
            character_16_multiplier = 0.70
            character_8_multiplier = 0.50
            character_4_multiplier = 0.45
            for i, a in enumerate(character_map):
                if np.any((a_nan := np.isnan(a))):
    
                    assert np.all(a_nan), "This indicates a bug in the original code. Please report this to the repository including this entire error message."
                else:
                    a = np.round(a * -7)
                    if i == 0:
                        a = np.round(a * (zone_scene["zone"].character_max_roi_boost / 1.75 * character_key_multiplier) + uniform_offset)
                    elif i % 8 == 0:
                        a = np.round(a * (zone_scene["zone"].character_max_roi_boost / 1.75 * character_32_multiplier) + uniform_offset)
                    elif i % 4 == 0:
                        a = np.round(a * (zone_scene["zone"].character_max_roi_boost / 1.75 * character_16_multiplier) + uniform_offset)
                    elif i % 2 == 0:
                        a = np.round(a * (zone_scene["zone"].character_max_roi_boost / 1.75 * character_8_multiplier) + uniform_offset)
                    else:
                        a = np.round(a * (zone_scene["zone"].character_max_roi_boost / 1.75 * character_4_multiplier) + uniform_offset)
                    roi_map.append([i * 4, a])

                    if i != character_map.shape[0] - 1:
                        roi_map.append([i * 4 + 1, np.full_like(a, np.round(uniform_nonboosting_offset), dtype=np.float32)])
                    else:
                        roi_map.append([i * 4 + 1, np.full_like(a, np.round(uniform_ending_nonboosting_offset), dtype=np.float32)])

            needed_offset = 0
            for line in roi_map:
                needed_offset = np.max([needed_offset, 0 - np.max(line[1])])
            for line in roi_map:
                line[1] += needed_offset
            crf -= needed_offset / 4
            if verbose >= 1:
                print(f"ROI map {crf:>5.2f} / ", end="", flush=True)

            roi_map_file = roi_maps_dir / f"roi-map-{scene_rjust(scene_n)}.txt"
            with roi_map_file.open("w") as roi_map_f:
                for line in roi_map:
                    roi_map_f.write(f"{line[0]} ")
                    np.savetxt(roi_map_f, line[1].reshape((1, -1)), fmt="%d")

        character_hiritsu = character_kyara["scenes"][scene_n]["kyara"]
        character_hiritsu = np.interp(character_hiritsu, [0.00, 0.06, 0.26, 0.36, 0.46, 0.56],
                                                         [0.00, 0.46, 1.00, 1.00, 0.96, 0.76])
        crf -= zone_scene["zone"].character_max_crf_boost * character_hiritsu
        if verbose >= 1:
            print(f"--crf {crf:>5.2f} / ", end="", flush=True)

        character_map_non_still = character_map[np.any(~np.isnan(character_map), axis=1)]
        if character_map_non_still.shape[0] >= 2:
            character_map_non_still_diff = np.sum(np.abs(np.diff(character_map_non_still, axis=0)))
            character_map_sum = np.sum(((sum_non_still := np.sum(character_map_non_still, axis=1))[1:] + sum_non_still[:-1]) / 2) / (character_map_non_still.shape[0] - 1) * (character_map.shape[0] - 1)
            if character_map_sum != 0.0:
                character_diff = character_map_non_still_diff / character_map_sum / 0.12
            else:
                character_diff = 0.0
        else:
            character_diff = 0.0
        if character_diff > 1.00:
            character_diff = 1.00
        crf -= zone_scene["zone"].character_max_motion_crf_boost * character_diff
        if verbose >= 1:
            print(f"motion --crf {crf:>5.2f} / ", end="", flush=True)

    crf = np.max([crf, zone_scene["zone"].final_min_crf])
    crf = np.round(crf / 0.25) * 0.25
    if verbose >= 1:
        print(f"Final {f"{crf:>5.2f}" if zone_scene["zone"].quarterstep_crf else f"{crf:.0f}"}", end="\n", flush=True)

    final_crf_frames[np.min([math.floor(crf / 10), final_crf_frames.shape[0] - 1])] += zone_scene["end_frame"] - zone_scene["start_frame"]

    final_scenes["scenes"][scene_n]["zone_overrides"] = {
        "encoder": "svt_av1",
        "passes": 1,
        "video_params": [
            "--crf", (f"{crf:.2f}" if zone_scene["zone"].quarterstep_crf else f"{crf:.0f}"),
            "--preset", f"{preset}",
            *zone_scene["zone"].final_dynamic_parameters(crf)
        ],
        "photon_noise": zone_scene["zone"].final_dynamic_photon_noise(scene_detection_average[zone_scene["start_frame"]:zone_scene["end_frame"]],
                                                                      scene_detection_min[zone_scene["start_frame"]:zone_scene["end_frame"]],
                                                                      scene_detection_max[zone_scene["start_frame"]:zone_scene["end_frame"]]),
        "photon_noise_height": zone_scene["zone"].final_photon_noise_height,
        "photon_noise_width": zone_scene["zone"].final_photon_noise_width,
        "chroma_noise": zone_scene["zone"].final_chroma_noise,
        "extra_splits_len": zone_scene["zone"].scene_detection_extra_split,
        "min_scene_len": zone_scene["zone"].scene_detection_min_scene_len
    }
    if zone_scene["zone"].character_enable and zone["zone"].character_max_roi_boost:
        final_scenes["scenes"][scene_n]["zone_overrides"]["video_params"] += ["--roi-map-file", str(roi_map_file)]
    
final_scenes["split_scenes"] = final_scenes["scenes"]
with scenes_file.open("w") as scenes_f:
    json.dump(final_scenes, scenes_f, cls=NumpyEncoder)

print(f"\r\033[K{scene_frame_print(scene_n)} / Boost calculation complete / {(scene_n + 1) / (time() - start):.0f} scenes per second", end="\n")

for section in range((nonzero_crf_frames := np.nonzero(final_crf_frames)[0])[0], nonzero_crf_frames[-1] + 1):
    print(f"\r\033[KFrame [{frame_rjust(scenes["scenes"][0]["start_frame"])}:{frame_rjust(scenes["scenes"][-1]["end_frame"])}] / Boosting result", end="")
    if section == final_crf_frames.shape[0] - 1:
        print(f" / --crf  {section * 10:.2f}+         ", end="")
    else:
        print(f" / --crf [{section * 10:>5.2f} ~ {(section + 1) * 10 - 0.25:>5.2f}] ", end="")
    print(f"{frame_rjust(final_crf_frames[section])} frames", end="\n")

print(f"\r\033[KTime {datetime.now().time().isoformat(timespec="seconds")} / Progression Boost finished", end="\n")
