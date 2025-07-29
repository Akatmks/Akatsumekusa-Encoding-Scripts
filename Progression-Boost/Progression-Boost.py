#!/usr/bin/env python3

# Progression Boost
# Copyright (c) Akatsumekusa and contributors
# Thanks to Ironclad and their grav1an, Miss Moonlight and their Lav1e,
# Trix and their autoboost, and BoatsMcGee and their Normal-Boost.


# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# The guide and config starts approximately 50 lines below this. Start
# reading from there.
#
# Also, if you don't want to do a lot of tinkering and just want to get  # <<<<  Do you want a good result fast?  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# a good result fast (one that's better than av1an's                     # <<<<  This pattern will guide you to only the necessary  <<<<<<<<<<<
# `--target-quality`!). You would only need to change about three        # <<<<  settings.  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# options below. Go down, and only read paragraphs that have arrows on   # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# the right just like this very paragraph. There will be more guides     # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# below to lead you!                                                     # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------


import argparse
from collections.abc import Callable
from datetime import datetime
import json
import math
import numpy as np
from numpy.random import default_rng
import os
from pathlib import Path
import platform
import subprocess
from time import time
from typing import Optional
import traceback
import vapoursynth as vs
from vapoursynth import core

if platform.system() == "Windows":
    os.system("")

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        else:
            return super(NumpyEncoder, self).default(obj)

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
parser.add_argument("--verbose", action="store_true", help="Progression Boost by default only reports scenes that have received big boost, or scenes that have built unexpected polynomial model. By enabling this option, all scenes will be reported")
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


class UnreliableSummarisationError(Exception):
    def __init__(self, score, message):
        super().__init__(message)
        self.score = score


# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Before everything, the codes above are for commandline arguments.      # <<<<  Do you want a good result fast?  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# The commandline arguments are only for specifying inputs and outputs   # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# while all encoding settings need to be modified within the script      # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# starting below.                                                        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# 
# To run the script, use `python Progression-Boost.py --input 01.mkv     # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# --output-scenes 01.scenes.json --temp 01.boost.tmp`, or read the help  # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# for all commandline arguments using `python Progression-Boost.py       # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# --help`.                                                               # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
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
#
# That's said, if you don't want a lot of tinkering, and you want to     # <<<<  Do you want a good result fast?  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# get a result fast, provided that you've selected a proper preset, the  # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# only thing you would need to adjust is the following three variables.  # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# Search for this in the file, set it to fit your needs, and you're      # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# good to go!                                                            # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# * `testing_parameters`                                                 # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# * `final_parameters`                                                   # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# * `metric_target`                                                      # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
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
    scene_detection_vapoursynth_method = "wwxd_scxvid".lower() # Preferred
    # scene_detection_vapoursynth_method = "wwxd".lower() # Fast
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
# detection here as  default and then use the builtin_av1an zone for OP
# and ED.

# You can also provide your own scene detection via `--input-scenes`.
# You must uncomment the above two options and uncomment this option
# for it to work.
    # scene_detection_method = "external".lower()

# Zoning information: all three `scene_detection_method` is zoneable,
# which means you can mix av1an based scene detection with VapourSynth
# based scene detection, as well as external scene detection fed from
# `--input-scenes`. However, `scene_detection_av1an_parameters` is not
# zoneable. There would only be one av1an scene detection pass.
# ---------------------------------------------------------------------
# Specify the desired scene length for scene detection. The result from
# this scene detection will be used both for test encodes and the final
# encodes.
    scene_detection_extra_split = 192
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
    scene_detection_target_split = 33

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
    metric_max_crf = 40.00
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
    def metric_unreliable_model_fallback_crf(self):
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

# At last, if you've disabled this Progression Boost module, and you
# only want Character Boost, set a base `--crf` here. This value has no
# effect if Progression Boost module is enabled.
    metric_unboosted_crf = 27.00

# Although we already clamp once for Progression Boost module above,
# the Character Boost module might also boost the `--crf` value. Let's
# clamp this one last time.
# This clamp is applied after both Progression Boost and Character
# Boost has finished.
    final_min_crf = 6.50
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
# default `--preset 7` or at most `--preset 6` is safe enough. Boosting
# should never take more than one third of the entire encoding time. If
# you have more time, you should use a slower `--preset` for final
# encoding pass and don't waste time on boosting.
    probing_preset = 6

# We'll now set the `--preset` for the output scenes file for our
# eventual final encode. Put your `--preset` after the `return` below,
# and you'll be good to go.
#
# Some of us may prefer using a mix of different `--preset`s, either
# because some of our parameters will be safer at slower `--preset`
# when the scene has very high (bad) `--crf`, or because one `--preset`
# is too fast for our target encoding time, and the next `--preset` is
# too slow.
# To support dynamic `--preset`, this is a function that receives a
# `--crf`, and should return a `--preset` for final encode.
# Note that this function is performed at the very last stage of this
# boosting script, hence the `final_` prefix instead of `metric_`
# prefix, which means the `--crf` this function receives not only
# includes `--crf` result from this Progression Boost module after
# `metric_dynamic_crf`, but also the `--crf` boosts in the next
# Character Boost module as well.
    def final_dynamic_preset(self, crf: float) -> int:
        return 0
# ---------------------------------------------------------------------
# Third, every other parameters:

# We've set `--crf` and `--preset`, and now we're setting all the
# remaining parameters.
# 
# For `final_dynamic_parameters`, use every parameters you plan to use
# for your eventual final encode, but:
#   Do not set `--crf` and `--preset` for `final_dynamic_parameters`,
#   because we've already set it above.
#   Do not set `-i` and `-b` and use the same parameters as you would
#   feed into av1an `--video-params`.
# For `probing_dynamic_parameters`, use the same parameters you as
# `final_dynamic_parameters`, but:
#   Do not set `--crf` and `--preset` for `probing_dynamic_parameters`,
#   because we've already set it above.
#   Do not set `-i` and `-b` and use the same parameters as you would
#   feed into av1an `--video-params`.
#   Set `--film-grain 0` for `probing_dynamic_parameters` if it is
#   nonzero in `final_dynamic_parameters`. `--film-grain` is a
#   generative process and we will get metric results that doesn't
#   match our visual experience.
#
# If you want to set a set of fixed parameters, fill it in directly
# after the `return` token.
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
# Character Boost module as well.
    def probing_dynamic_parameters(self, crf: float) -> list[str]:
        return """--lp 3 --keyint -1 --input-depth 10 --scm 0
                  --tune 3 --qp-min 8 --chroma-qp-min 10
                  --complex-hvs 0 --psy-rd 1.0 --spy-rd 0
                  --color-primaries 1 --transfer-characteristics 1 --matrix-coefficients 1 --color-range 0""".split()
    def final_dynamic_parameters(self, crf: float) -> list[str]:
        return """--lp 3 --keyint -1 --input-depth 10 --scm 0
                  --tune 3 --qp-min 8 --chroma-qp-min 10
                  --complex-hvs 1 --psy-rd 1.0 --spy-rd 0
                  --color-primaries 1 --transfer-characteristics 1 --matrix-coefficients 1 --color-range 0""".split()
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
              + f" -y --chunk-method {self.source_provider} --encoder svt-av1 --concat mkvmerge --force --no-defaults --video-params").split() + \
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
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Once the test encodes finish, Progression Boost will start
# calculating metric for each scenes.

# When calculating metric, we don't need to calculate it for every
# single frame. It's very common for anime to have 1 frame of animation
# every 2 to 3 frames. It's not only meaningless trying to calculate
# repeating frames, it's actually dangerous because it will dilute the
# data and make the few bad frames less arithmetically significant.
#
# We will first pick a few frames with the highest diffs. These are the
# frames that are most likely to be bad. However, the fact that this
# disproportionately picks the bad frames means it would not be very
# representative if you're using a mean-based method to summarise the
# data later. Keep the number of frames picked here at a modest amount
# if you're using a mean-based method. If you're using a percentile-
# based method to boost the worst frames, you can consider picking half
# of the frames you're measuring here. Although do note that this way
# the percentile you're measuring no longer represents the percentile
# of the whole scene, but just the percentile of the frames you pick.
    metric_highest_diff_frames = 8
# We will avoid selecting frames too close to each other to avoid
# picking all the frames from, let's say, a fade at the start or the
# end of the scene.
    metric_highest_diff_min_separation = 4
#
# Then we will separate the frames into two brackets at 2 times MAD but
# based on the 40th percentile instead of mean value. The lower bracket
# are most likely be repeating frames that are the same as their
# previous frames, and the upper bracket are most likely to be frames
# we want to measure.
# A good starting point for a mean-based method is to measure 6 and 3
# frames respectively from each bracket. If you have the computing
# power and you want to be relatively safe, use maybe 10 and 5. If you
# want to speed up metric calculation, you can try 4 and 2 for these
# while also reducing `metric_highest_diff_frames` to 2.
    metric_upper_diff_bracket_frames = 16
    metric_lower_diff_bracket_frames = 0
# We select frames from the two brackets randomly, but we want to avoid
# picking a frame in the lower bracket right after a frame from the
# upper bracket, because these two frames are most likely exactly the
# same.
    metric_lower_diff_bracket_min_separation = 2
# If there are not enough frames in the upper bracket to select, we
# will select some more frames in the lower diff bracket. If the number
# of frames selected in the upper diff bracket is smaller than this
# number, we will select additional frames in the lower bracket until
# this number is reached.
    metric_upper_diff_bracket_fallback_frames = 10
#
# All these diff sorting and selection excludes the first frame of the
# scene since the diff data of the first frame is compared against the
# last frame from the previous scene and is irrelevant. In addition,
# the first frame as the keyframe often has great quality. Do you want
# to always include the first frame in metric calculation?
    metric_first_frame = 0
#
# Sometimes, sometimes SVT-AV1-PSY will encode the last frame of a
# scene slightly worse than the rest of the frames. Do you want to
# always include the first frame in metric calculation?
    metric_last_frame = 1
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Progression Boost currently supports two methods calculating metrics,
# FFVship and VapourSynth.
# FFVship is a standalone external program, while VapourSynth method
# supports vship and vszip.

# FFVship is only available if you've not applied filtering via
# `--encode-input`, and you don't plan to apply additional filtering
# before calculating metric. FFVship is faster than using vship in
# VapourSynth.
# Enable FFVship by commenting the line for VapourSynth below and
# uncommenting the line below.
    metric_method = "ffvship".lower()

# If you want to use VapourSynth based methods for calculating metrics,
# comment the line above for FFVship and uncomment the line below.
    # metric_method = "vapoursynth".lower()
#
# For VapourSynth based metric calculation, if you've applied filtering
# via `--encode-input`, you can match it and apply the same filtering
# here:
    metric_reference = source_clip
#
# For VapourSynth based metric calculation, this function allows you to
# perform some additional filtering before calculating metrics.
    def metric_process(self, clips: list[vs.VideoNode]) -> list[vs.VideoNode]:
# First, here is a hack if you want higher speed calculating metrics.
# What about cropping the clip from 1080p to 900p or 720p? This is
# tested to have been working very well, producing very similar final
# `--crf`swhile increasing measuring speed significantly. However,
# since we are cropping away outer edges of the screen, for most anime,
# we will have proportionally more characters than backgrounds in the
# cropped compare. This may not may not be preferrable. If you want to
# enable cropping, uncomment the lines below to crop the clip to 900p
# before comparing.
    #     for i in range(len(clips)):
    #         clips[i] = clips[i].std.Crop(left=160, right=160, top=90, bottom=90)
# If you want some other processing before calculating metrics, you can
# implement it here.
        return clips
# ---------------------------------------------------------------------
# What metric do you want to use?

# To use Butteraugli 3Norm via FFVship or vship, uncomment the lines
# below.
    # metric_ffvship_calculate = "Butteraugli"
    # metric_ffvship_metric = lambda self, frame: frame[1]
    # metric_vapoursynth_calculate = core.vship.BUTTERAUGLI
    # metric_vapoursynth_metric = lambda self, frame: frame.props["_BUTTERAUGLI_3Norm"]
    # metric_better_metric = np.less

# To use Butteraugli INFNorm via FFVship or vship, uncomment the lines
# below.
    # metric_ffvship_calculate = "Butteraugli"
    # metric_ffvship_metric = lambda self, frame: frame[2]
    # metric_vapoursynth_calculate = core.vship.BUTTERAUGLI
    # metric_vapoursynth_metric = lambda self, frame: frame.props["_BUTTERAUGLI_INFNorm"]
    # metric_better_metric = np.less

# During testing, we found that Butteraugli 3Norm with a tiny spice of
# Butteraugli INFNorm performs very well when targeting high quality
# targets. Butteraugli 3Norm ensures a good baseline measurement, while
# the tiny spice of Butteraugli INFNorm patches some of the small
# issues Butteraugli 3Norm missed.
    metric_ffvship_calculate = "Butteraugli"
    metric_ffvship_metric = lambda self, frame: frame[1] * 0.975 + frame[2] * 0.025
    metric_vapoursynth_calculate = core.vship.BUTTERAUGLI
    metric_vapoursynth_metric = lambda self, frame: frame.props["_BUTTERAUGLI_3Norm"] * 0.975 + frame.props["_BUTTERAUGLI_INFNorm"] * 0.025
    metric_better_metric = np.less

# To use SSIMU2 via FFVship or vship, uncomment the lines below.
    # metric_ffvship_calculate = "SSIMULACRA2"
    # metric_ffvship_metric = lambda self, frame: frame[0]
    # metric_vapoursynth_calculate = core.vship.SSIMULACRA2
    # metric_vapoursynth_metric = lambda self, frame: frame.props["_SSIMULACRA2"]
    # metric_better_metric = np.greater

# To use SSIMU2 via vszip, uncomment the lines below.
    # metric_vapoursynth_calculate = core.vszip.SSIMULACRA2
    # metric_vapoursynth_metric = lambda self, frame: frame.props["SSIMULACRA2"]
    # metric_better_metric = np.greater
# ---------------------------------------------------------------------
# After calcuating metric for frames, we summarise the quality for each
# scene into a single value. There are three common way for this.
# 
# The first is the percentile method. The percentile method is better
# at getting bad frames good.
# With an aggressive observation such as observing 10th percentile or
# lower, in tests, we have had the worst single frame to be within 3
# to 4 SSIMU2 away from the mean. Compared to the normal 15 or more
# without boosting, boosting using the percentile method ensures that
# even the bad frames are decent.
# A note is that if you want to get the best quality, you should also
# increase the number of frames to measured specified above in order to
# prevent random bad frames from slipping through.
# When targeting lower quality targets, a looser observation such as
# observing the 20th or the 30th percentile should also produce a decent
# result.
# 
# Note that Progression Boost by default uses median-unbiased estimator
# for calculating percentile, which is much more sensitive to extreme
# values than linear estimator.
    # def metric_summarise(self, scores: np.ndarray[np.float32]) -> np.float32:
    #     percentile = 15
    #     return np.percentile(scores, percentile, method="median_unbiased")

# The percentile method is also tested on Butteraugli 3Norm score, use
# 90th percentile instead of 10th, and 80th percentile instead of 20th,
# and you are good to go.
    # def metric_summarise(self, scores: np.ndarray[np.float32]) -> np.float32:
    #     percentile = 80
    #     return np.percentile(scores, percentile, method="median_unbiased")

# The second method is even more aggressive than the first method, to
# take the minimum or the maximum value from all the frames measured.
# This is the default for the preset targeting the highest quality,
# Preset-Butteraugli-3Norm-INFNorm-Max.
# A note is that if you want to get the best quality, you should also
# increase the number of frames to measured specified above in order to
# prevent random bad frames from slipping through.
    # def metric_summarise(self, scores: np.ndarray[np.float32]) -> np.float32:
    #     return np.min(scores)
    def metric_summarise(self, scores: np.ndarray[np.float32]) -> np.float32:
        return np.max(scores)

# The second method is to calculate a mean value for the whole scene.
# For SSIMU2 score, harmonic mean is studied by Miss Moonlight to have
# good representation of realworld viewing experience, and ensures a
# consistent quality thoughout the encode without bloating too much for
# the worst frames.
# In tests using harmonic mean method, we've observed very small
# standard deviation of less than 2.000 in the final encode, compared to
# a normal value of 3 to 4 without boosting.
#
# There is a very rare edge case for harmonic mean, that when the score
# for a single frame dropped too low, it can skew the whole mean value
# to the point that scores for all other frames have essentially no
# effects on the final score. For this reason, we cap the SSIMU2 score to
# 10 before calculating harmonic mean. 
#
# To use the harmonic mean method, comment the lines above for the
# percentile method, and uncomment the lines below.
    # def metric_summarise(self, scores: np.ndarray[np.float32]) -> np.float32:
    #     if np.any((small := scores < 15)):
    #         scores[small] = 15
    #         raise UnreliableSummarisationError(scores.shape[0] / np.sum(1 / scores), f"Frames in this scene receive a metric score below 15 for test encodes. This may result in overboosting")
    #     else:
    #         return scores.shape[0] / np.sum(1 / scores)

# For Butteraugli 3Norm score, root mean cube is suggested by Miss
# Moonlight and tested to have good overall boosting result.
#
# To use the root mean cube method, comment the lines above for the
# percentile method, and uncomment the two lines below.
    # def metric_summarise(self, scores: np.ndarray[np.float32]) -> np.float32:
    #     return np.mean(scores ** 3) ** (1 / 3)

# If you want to use a different method than above to summarise the
# data, implement your own method here.
# 
# This function is called independently for every scene for every test
# encode.
    # def metric_summarise(self, scores: np.ndarray[np.float32]) -> np.float32:
    #     pass
# ---------------------------------------------------------------------
# After calculating the percentile, or harmonic mean, or other           # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# quantizer of the data, we fit the quantizers to a polynomial model     # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# and try to predict the lowest `--crf` that can reach the target        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# quality we're aiming at.                                               # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# Specify the target quality using the variable below.                   # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#
# Note that Progression Boost can only create the model based on test    # <<<<  These three parameters are all you need to get a good  <<<<<<<
# encodes performed at `--preset 7` by default. You will get much        # <<<<  result fast, but you are recommended to have a look at  <<<<<<
# better result in your final encode using a slower `--preset`. You      # <<<<  all the other settings once you become familiar with the <<<<<
# should account for this difference when setting the number below.      # <<<<  script. There's still a lot of improvements, timewise or  <<<<
# Maybe set it a little bit lower than your actual target.               # <<<<  qualitywise, you can have with all the other options.  <<<<<<<
    metric_target = 0.620
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
# Enable character boosting by setting the line below to True.
    character_enable = True
# ---------------------------------------------------------------------
# Set how aggressive character boosting should be.
# This first value is for the ROI map based boosting. It's the same
# scale as `--crf`. In a sense the default `5.00` means the biggest
# character boost is 5 `--crf` better than the background. Or if you're
# familiar with the internals of SVT-AV1 derived encoder, it's more
# accurate to say the Q of Super Block with characters can be at most
# 20 better than Super Block containing only backgrounds using the
# default `5.00` sigma.
#
# The maximum recommended value for this is 7.00 ~ 8.00. If you want
# more aggressive character boosting, applying them via the second
# value for `--crf` based boosting should be more effective.
#
# This maximum boost is only applied to the first frame of a scene.
# Later frames will be boosted less depending on how the hierarchial
# structure is commonly constructed.
#
# The number here should be positive.
    character_max_roi_boost = 5.00
# This second value is for the `--crf` based character boosting. It
# boosts a scene depending on how much percentage of the screen is
# occupied by characters.
#
# You can set this value as high as you want.
# You can even disable Progression Boost module, only relying on the
# base `--crf` set by `metric_unboosted_crf` to maintain a baseline
# consistency and hyperboost character by setting something like
# `15.00` here.
#
# The number here should be positive.
    character_max_crf_boost = 4.00
# ---------------------------------------------------------------------
# Select vs-mlrt backend for image segmentation model:
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
                  --tune 3 --qp-min 8 --chroma-qp-min 10
                  --film-grain 12 --complex-hvs 1 --psy-rd 1.0 --spy-rd 0
                  --color-primaries 1 --transfer-characteristics 1 --matrix-coefficients 1 --color-range 0""".split()
# Let's use a different `--preset` for final encode:
    def final_dynamic_preset(self, crf: float) -> int:
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
if zones_string is None:
    if zones_file:
        print(f"\033[31mInput `--zones` is empty. Continuing with no zoning...\033[0m")
    else:
        print(f"\033[31mInput `--zones-string` is empty. Continuing with no zoning...\033[0m")

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
        print(f"Skipping zones with out of bound start_frame {item[0]}...")

    if item[1] <= -2:
        raise ValueError(f"Invalid end_frame in the zones with value {item[1]}")
    if item[1] > zone_default.source_clip.num_frames:
        print(f"\033[31mOut of bound end_frame in the zones with value {item[1]}. Clamp end_frame for the zone to {zone_default.source_clip.num_frames}...\033[0m")
        print(f"Use `-1` as end_frame to silence this out of bound warning.")
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
            parser.print_usage()
            print("Progression Boost: error: the following argument is required when `scene_detection_method` is set to `\"external\"` in zones: --input-scenes")
            raise SystemExit(2)
        
        break
else:
    if input_scenes_file:
        print("Progression Boost: warn: the following argument is provided but there are no zones where `scene_detection_method` is set to `\"external\"`: --input-scenes")

for zone in zones:
    if zone["zone"].character_enable:
        if not roi_maps_dir:
            parser.print_usage()
            print("Progression Boost: error: the following argument is required when Character Boost is enabled: --output-roi-maps")
            raise SystemExit(2)
        roi_maps_dir.mkdir(parents=True, exist_ok=True)

        character_backend = zone_default.character_get_backend()
        character_model = zone_default.character_get_model()

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


# Scene dectection
scene_detection_scenes_file = scene_detection_temp_dir.joinpath("scenes.json")
scene_detection_av1an_scenes_file = scene_detection_temp_dir.joinpath("av1an.scenes.json")
scene_detection_diffs_file = scene_detection_temp_dir.joinpath("luma-diff.txt")
scene_detection_average_file = scene_detection_temp_dir.joinpath("luma-average.txt")
scene_detection_min_file = scene_detection_temp_dir.joinpath("luma-min.txt")
scene_detection_max_file = scene_detection_temp_dir.joinpath("luma-max.txt")

scene_detection_diffs_available = False
if resume and scene_detection_diffs_file.exists() and \
              scene_detection_average_file.exists() and \
              scene_detection_min_file.exist() and \
              scene_detection_max_file.exist():
    scene_detection_diffs = np.loadtxt(scene_detection_diffs_file, dtype=np.float32)
    scene_detection_average = np.loadtxt(scene_detection_average_file, dtype=np.float32)
    scene_detection_min = np.loadtxt(scene_detection_min_file, dtype=np.float32)
    scene_detection_max = np.loadtxt(scene_detection_max_file, dtype=np.float32)
    scene_detection_diffs_available = True


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
            "--temp", str(scene_detection_temp_dir.joinpath("av1an.tmp")),
            "-i", str(input_file),
            "--scenes", str(scene_detection_av1an_scenes_file),
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
            print(f"\r\033[KFrame {current_frame} / Measuring frame luma / {current_frame / (time() - start):.02f} fps", end="\r")
            scene_detection_diffs[current_frame] = frame.props["LumaDiff"]
            scene_detection_average[current_frame] = frame.props["LumaAverage"]
            scene_detection_min[current_frame] = frame.props["LumaMin"]
            scene_detection_max[current_frame] = frame.props["LumaMax"]
        print(f"\r\033[KFrame {current_frame + 1} / Frame luma measurement complete / {(current_frame + 1) / (time() - start):.02f} fps", end="\n")
        
        np.savetxt(scene_detection_diffs_file, scene_detection_diffs, fmt="%.9f")
        np.savetxt(scene_detection_average_file, scene_detection_average, fmt="%.9f")
        np.savetxt(scene_detection_min_file, scene_detection_min, fmt="%.9f")
        np.savetxt(scene_detection_max_file, scene_detection_max, fmt="%.9f")
        scene_detection_diffs_available = True

    if not scene_detection_diffs_available:
        if scene_detection_perform_av1an or \
           (scene_detection_perform_vapoursynth and not scene_detection_has_av1an and not scene_detection_has_external):
            scene_detection_measure_frame_luma()

    
    if scene_detection_perform_vapoursynth:
        if not scene_detection_diffs_available:
            scene_detection_diffs = np.empty((zone_default.source_clip.num_frames,), dtype=np.float32)
            scene_detection_average = np.empty((zone_default.source_clip.num_frames,), dtype=np.float32)
            scene_detection_min = np.empty((zone_default.source_clip.num_frames,), dtype=np.float32)
            scene_detection_max = np.empty((zone_default.source_clip.num_frames,), dtype=np.float32)

        scene_detection_rjust_digits = math.floor(np.log10(zone_default.source_clip.num_frames)) + 1
        scene_detection_rjust = lambda frame: str(frame).rjust(scene_detection_rjust_digits)

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
                    print(f"\r\033[KFrame {current_frame} / Detecting scenes / {offset_frame / (time() - start):.02f} fps", end="")

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
                        if not luma_scenecut_prev:
                            luma_scenecut = scene_detection_min[current_frame] > 231.125 * 2 ** (scene_detection_bits - 8) or \
                                            scene_detection_max[current_frame] < 19.875 * 2 ** (scene_detection_bits - 8)
                        else:
                            luma_scenecut = scene_detection_min[current_frame] > 229.125 * 2 ** (scene_detection_bits - 8) or \
                                            scene_detection_max[current_frame] < 21.875 * 2 ** (scene_detection_bits - 8)
                    elif zone["zone"].scene_detection_vapoursynth_range == "full":
                        if not luma_scenecut_prev:
                            luma_scenecut = scene_detection_min[current_frame] > 251.125 * 2 ** (scene_detection_bits - 8) or \
                                            scene_detection_max[current_frame] < 3.875 * 2 ** (scene_detection_bits - 8)
                        else:
                            luma_scenecut = scene_detection_min[current_frame] > 249.125 * 2 ** (scene_detection_bits - 8) or \
                                            scene_detection_max[current_frame] < 5.875 * 2 ** (scene_detection_bits - 8)

                    if luma_scenecut and not luma_scenecut_prev:
                        diffs[offset_frame] = scene_detection_diffs[current_frame] + 2.0
                    else:
                        diffs[offset_frame] = scene_detection_diffs[current_frame] + scene_detection_scenecut

                    luma_scenecut_prev = luma_scenecut

                zones_diffs[zone_i] = diffs

        print(f"\r\033[KFrame {current_frame + 1} / VapourSynth based scene detection complete", end="\n")

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
                    print(f"\r\033[KFrame [{scene_detection_rjust(av1an_scene["start_frame"])}:{scene_detection_rjust(av1an_scene["end_frame"])}] / Creating scenes", end="")
                    scenes["scenes"].append(av1an_scene)

        elif zone["zone"].scene_detection_method == "external":
            external_scenes_start_copying = False
            for external_scene in scene_detection_external_scenes["scenes"]:
                assert "start_frame" in external_scene and "end_frame" in external_scene, "Invalid scenes file from `--input-scenes`"

                if external_scene["start_frame"] >= zone["start_frame"]:
                    if not external_scenes_start_copying and external_scene["start_frame"] > zone["start_frame"]:
                        if not zone["zone"].metric_enable and external_scene["end_frame"] - zone["start_frame"] < 5:
                            print(f"\r\033[KFrame [{scene_detection_rjust(zone["start_frame"])}:{scene_detection_rjust(external_scene["end_frame"])}] / A scene from `--input-scenes` is cut off by zone boundary into a scene shorter than 5 frames. As Progression Boost module is disabled for the zone, this scene might get poorly encoded.", end="\n")
                
                        scenes["scenes"].append({"start_frame": zone["start_frame"],
                                                 "end_frame": external_scene["start_frame"],
                                                 "zone_overrides": None})
                                                 
                    external_scenes_start_copying = True

                if external_scenes_start_copying:
                    if external_scene["end_frame"] > zone["end_frame"]:
                        if not zone["zone"].metric_enable and zone["end_frame"] - external_scene["start_frame"] < 5:
                            print(f"\r\033[KFrame [{scene_detection_rjust(external_scene["start_frame"])}:{scene_detection_rjust(zone["end_frame"])}] / A scene from `--input-scenes` is cut off by zone boundary into a scene shorter than 5 frames. As Progression Boost module is disabled for the zone, this scene might get poorly encoded.", end="\n")
                        print(f"\r\033[KFrame [{scene_detection_rjust(external_scene["start_frame"])}:{scene_detection_rjust(zone["end_frame"])}] / Creating scenes", end="")
                        scenes["scenes"].append({"start_frame": external_scene["start_frame"],
                                                 "end_frame": zone["end_frame"],
                                                 "zone_overrides": None})
                    else:
                        print(f"\r\033[KFrame [{scene_detection_rjust(external_scene["start_frame"])}:{scene_detection_rjust(external_scene["end_frame"])}] / Creating scenes", end="")
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
            great_diffs = diffs.copy()
            great_diffs[great_diffs < 1.0] = 0
            great_diffs_sort = np.argsort(great_diffs, stable=True)[::-1]

            def scene_detection_split_scene(start_frame, end_frame):
                print(f"\r\033[KFrame [{scene_detection_rjust(start_frame + zone["start_frame"])}:{scene_detection_rjust(end_frame + zone["start_frame"])}] / Creating scenes", end="")

                if end_frame - start_frame <= zone["zone"].scene_detection_target_split or \
                   end_frame - start_frame < 2 * zone["zone"].scene_detection_min_scene_len:
                    return [start_frame]

                if end_frame - start_frame <= 2 * zone["zone"].scene_detection_target_split:
                    for current_frame in great_diffs_sort:
                        if great_diffs[current_frame] < 1.16:
                            break
                        if current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len and \
                           current_frame - start_frame <= zone["zone"].scene_detection_target_split and end_frame - current_frame <= zone["zone"].scene_detection_target_split:
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                if end_frame - start_frame <= zone["zone"].scene_detection_extra_split:
                    for current_frame in great_diffs_sort:
                        if great_diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           (current_frame - start_frame <= zone["zone"].scene_detection_target_split or end_frame - current_frame <= zone["zone"].scene_detection_target_split):
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in great_diffs_sort:
                        if great_diffs[current_frame] < 1.16:
                            return [start_frame]
                        if current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len:
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                else: # end_frame - start_frame > zone["zone"].scene_detection_extra_split
                    for current_frame in great_diffs_sort:
                        if great_diffs[current_frame] < 1.12:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split + 0.15):
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in great_diffs_sort:
                        if great_diffs[current_frame] < 1.16:
                            break
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           (current_frame - start_frame <= zone["zone"].scene_detection_target_split or end_frame - current_frame <= zone["zone"].scene_detection_target_split):
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in great_diffs_sort:
                        if great_diffs[current_frame] < 1.16:
                            break
                        if current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len:
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                    for current_frame in diffs_sort:
                        if (current_frame - start_frame >= zone["zone"].scene_detection_min_scene_len and end_frame - current_frame >= zone["zone"].scene_detection_min_scene_len) and \
                           math.ceil((current_frame - start_frame) / zone["zone"].scene_detection_extra_split) + \
                           math.ceil((end_frame - current_frame) / zone["zone"].scene_detection_extra_split) <= \
                           math.ceil((end_frame - start_frame) / zone["zone"].scene_detection_extra_split):
                            return scene_detection_split_scene(start_frame, current_frame) + \
                                   scene_detection_split_scene(current_frame, end_frame)

                assert False, "This indicates a bug in the original code. Please report this to the repository including this entire error message."

            start_frames = scene_detection_split_scene(0, len(diffs))

            start_frames += [zone["end_frame"] - zone["start_frame"]]
            for i in range(len(start_frames) - 1):
                scenes["scenes"].append({"start_frame": start_frames[i] + zone["start_frame"],
                                         "end_frame": start_frames[i + 1] + zone["start_frame"],
                                         "zone_overrides": None})

    print(f"\r\033[KFrame [{scenes["scenes"][-1]["start_frame"]}:{scenes["scenes"][-1]["end_frame"]}] / Scene creation complete", end="\n")

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

else:
    with scene_detection_scenes_file.open("r") as scenes_f:
        scenes = json.load(scenes_f)


raise SystemExit(0)





# During the first probe
if not scene_detection_diffs_available:
    scene_detection_measure_frame_luma()




# Testing
for n, crf in enumerate(testing_crfs):
    if not resume or not temp_dir.joinpath(f"test-encode-{n:0>2}.mkv").exists():
        temp_dir.joinpath(f"test-encode-{n:0>2}.mkv").unlink(missing_ok=True)
        temp_dir.joinpath(f"test-encode-{n:0>2}.lwi").unlink(missing_ok=True)

        # If you want to use a different encoder than SVT-AV1 derived ones, modify here. This is not tested and may have additional issues.
        command = [
            "av1an",
            "--temp", str(temp_dir.joinpath(f"test-encode-{n:0>2}.tmp")),
            "--keep"
        ]
        if resume:
            command += ["--resume"]
        command += [
            "-i", str(testing_input_file),
            "-o", str(temp_dir.joinpath(f"test-encode-{n:0>2}.mkv")),
            "--scenes", str(scene_detection_scenes_file),
            *testing_av1an_parameters.split(),
            "--video-params", f"--crf {crf:.2f} {testing_dynamic_parameters(crf)} {testing_parameters}"
        ]
        if testing_input_vspipe_args is not None:
            command += ["--vspipe-args"] + testing_input_vspipe_args
        try:
            subprocess.run(command, text=True, check=True)
        except subprocess.CalledProcessError:
            traceback.print_exc()
        assert temp_dir.joinpath(f"test-encode-{n:0>2}.mkv").exists()


# Metric
if zones_file:
    zones_f = zones_file.open("w")

# Ding
metric_iterate_crfs = np.append(testing_crfs, [final_max_crf, final_min_crf])
metric_reporting_crf = final_min_crf + 6.00

metric_scene_rjust_digits = math.floor(np.log10(len(scenes["scenes"]))) + 1
metric_scene_rjust = lambda scene: str(scene).rjust(metric_scene_rjust_digits, "0")
metric_frame_rjust_digits = math.floor(np.log10(metric_reference.num_frames)) + 1
metric_frame_rjust = lambda frame: str(frame).rjust(metric_frame_rjust_digits)
metric_scene_frame_print = lambda scene, start_frame, end_frame: f"Scene {metric_scene_rjust(scene)} Frame [{metric_frame_rjust(start_frame)}:{metric_frame_rjust(end_frame)}]"

metric_clips = [metric_reference] + \
               [core.lsmas.LWLibavSource(temp_dir.joinpath(f"test-encode-{n:0>2}.mkv").expanduser().resolve(),
                                         cachefile=temp_dir.joinpath(f"test-encode-{n:0>2}.lwi").expanduser().resolve()) for n in range(len(testing_crfs))]
metric_clips = metric_process(metric_clips)

if character_enable:
    character_clip = zone_default.source_clip

    character_block_width = math.ceil(character_clip.width / 64)
    character_block_height = math.ceil(character_clip.height / 64)
    character_clip = character_clip.resize.Bicubic(filter_param_a=0, filter_param_b=0.5, \
                                                   width=character_block_width*64, height=character_block_height*64, src_width=character_block_width*64, src_height=character_block_height*64, \
                                                   format=vs.RGBS, primaries_in=1, matrix_in=1, transfer_in=1, range_in=0, transfer=13, range=1)
    character_clip = vsmlrt.inference(character_clip, character_model, backend=character_backend)
    character_clip = character_clip.akarin.Expr("x 0.95 > x 0 ?")

    character_clip = character_clip.resize.Bicubic(filter_param_a=0, filter_param_b=0, \
                                                   width=character_block_width, height=character_block_height)
    character_clip = character_clip.akarin.Expr("x 2 *")
    character_clip = character_clip.akarin.Expr("""
x[-1,-1] x[-1,0] x[-1,1] x[0,-1] x[0,0] x[0,1] x[1,-1] x[1,0] x[1,1] + + + + + + + + 9 / avg!
avg@ x > avg@ x ? r!
r@ 1 < r@ 1 ? r!
r@ -1 > r@ -1 ?""")

start = time() - 0.000001
for i, scene in enumerate(scenes["scenes"]):
    print(f"\033[K{metric_scene_frame_print(i, scene["start_frame"], scene["end_frame"])} / Calculating boost / {i / (time() - start):.02f} scenes per second", end="\r")
    printing = False

    rng = default_rng(1188246) # Guess what is this number. It's the easiest cipher out there.

    # These frames are offset from `scene["start_frame"] + 1` and that's why they are offfset, not offset
    offfset_frames = []
    
    scene_diffs = scene_detection_diffs[scene["start_frame"] + 1:scene["end_frame"]]
    scene_diffs_sort = np.argsort(scene_diffs)[::-1]
    picked = 0
    for offfset_frame in scene_diffs_sort:
        if picked >= metric_highest_diff_frames:
            break
        to_continue = False
        for existing_frame in offfset_frames:
            if np.abs(existing_frame - offfset_frame) < metric_highest_diff_min_separation:
                to_continue = True
                break
        if to_continue:
            continue
        offfset_frames.append(offfset_frame)
        picked += 1
    
    if metric_last_frame >= 1 and scene["end_frame"] - scene["start_frame"] - 2 not in offfset_frames:
        offfset_frames.append(scene["end_frame"] - scene["start_frame"] - 2)

    scene_diffs_percentile = np.percentile(scene_diffs, 40, method="linear")
    scene_diffs_percentile_absolute_deviation = np.percentile(np.abs(scene_diffs - scene_diffs_percentile), 40, method="linear")
    scene_diffs_upper_bracket_ = np.argwhere(scene_diffs > scene_diffs_percentile + 5 * scene_diffs_percentile_absolute_deviation).reshape((-1))
    scene_diffs_lower_bracket_ = np.argwhere(scene_diffs <= scene_diffs_percentile + 5 * scene_diffs_percentile_absolute_deviation).reshape((-1))
    scene_diffs_upper_bracket = np.empty_like(scene_diffs_upper_bracket_)
    rng.shuffle((scene_diffs_upper_bracket__ := scene_diffs_upper_bracket_[:math.ceil(scene_diffs_upper_bracket_.shape[0] / 2)]))
    scene_diffs_upper_bracket[::2] = scene_diffs_upper_bracket__
    rng.shuffle((scene_diffs_upper_bracket__ := scene_diffs_upper_bracket_[-math.floor(scene_diffs_upper_bracket_.shape[0] / 2):]))
    scene_diffs_upper_bracket[1::2] =scene_diffs_upper_bracket__
    scene_diffs_lower_bracket = np.empty_like(scene_diffs_lower_bracket_)
    rng.shuffle((scene_diffs_lower_bracket__ := scene_diffs_lower_bracket_[:math.ceil(scene_diffs_lower_bracket_.shape[0] / 2)]))
    scene_diffs_lower_bracket[::2] = scene_diffs_lower_bracket__
    rng.shuffle((scene_diffs_lower_bracket__ := scene_diffs_lower_bracket_[-math.floor(scene_diffs_lower_bracket_.shape[0] / 2):]))
    scene_diffs_lower_bracket[1::2] = scene_diffs_lower_bracket__

    picked = 0
    for offfset_frame in scene_diffs_upper_bracket:
        if picked >= metric_upper_diff_bracket_frames:
            break
        if offfset_frame in offfset_frames:
            continue
        offfset_frames.append(offfset_frame)
        picked += 1
    
    if picked < metric_upper_diff_bracket_fallback_frames:
        to_pick = metric_lower_diff_bracket_frames + metric_upper_diff_bracket_fallback_frames - picked
    else:
        to_pick = metric_lower_diff_bracket_frames

    if metric_first_frame >= 1:
        offfset_frames.append(-1)

    picked = 0
    for offfset_frame in scene_diffs_lower_bracket:
        if picked >= to_pick:
            break
        to_continue = False
        for existing_frame in offfset_frames:
            if np.abs(existing_frame - offfset_frame) < metric_lower_diff_bracket_min_separation:
                to_continue = True
                break
        if to_continue:
            continue
        offfset_frames.append(offfset_frame)
        picked += 1
        
    frames = np.sort(offfset_frames) + (scene["start_frame"] + 1)

    clips = []
    for metric_clip in metric_clips:
        clip = metric_clip[int(frames[0])]
        for frame in frames:
            clip += metric_clip[int(frame)]
        clips.append(clip)
        
    printed = False
    quantisers = np.empty((len(testing_crfs),), dtype=float)
    for n in range(len(testing_crfs)):
        scores = np.array([metric_metric(frame) for frame in metric_calculate(clips[0], clips[n + 1]).frames()])
        try:
            quantisers[n] = metric_summarise(scores)
        except UnreliableSummarisationError as e:
            if not printed:
                print(f"\033[K{metric_scene_frame_print(i, scene["start_frame"], scene["end_frame"])} / Unreliable summarisation / {str(e)}")
                printed = True
                printing = True
            quantisers[n] = e.score

    try:
        model = metric_model(testing_crfs, quantisers)
    except UnreliableModelError as e:
        if not np.all(metric_better_metric(quantisers, metric_target)):
            print(f"\033[K{metric_scene_frame_print(i, scene["start_frame"], scene["end_frame"])} / Unreliable model / {str(e)}")
            printing = True
        model = e.model

    final_crf = None
    # This is in fact iterating metric_iterate_crfs, which is constructed above below the Ding comment.
    for n in range(len(testing_crfs) + 1):
        if metric_better_metric(model(metric_iterate_crfs[n]), metric_target):
            if n == len(testing_crfs):
                # This means even at final_max_crf, we are still higher than the target quality.
                # We will just use final_max_crf as final_crf. It shouldn't matter.
                final_crf = metric_iterate_crfs[n]
                break
            else:
                # This means the point where predicted quality meets the target is in higher crf ranges.
                # We will skip this range and continue.
                continue
        else:
            # Because we know from previous iteration that at metric_iterate_crfs[n-1], the predicted quality is higher than the target,
            # and now at metric_iterate_crfs[n], the prediceted quality is lower than the target,
            # this means the point where predicted quality meets the target is within this range between metric_iterate_crfs[n] and metric_iterate_crfs[n-1].
            # The only exception is when n == 0, while will be dealt with later.
            for crf in np.arange(metric_iterate_crfs[n] - 0.05, metric_iterate_crfs[n-1] - 0.005, -0.05):
                if metric_better_metric((value := model(crf - 0.005)), metric_target): # Also numeric instability stuff
                    # We've found the biggest --crf whose predicted quality is higher than the target.
                    final_crf = crf
                    break
            else:
                # The last item in the iteration is metric_iterate_crfs[n-1], and from outer loop we know that at that crf the predicted quality is higher than the target.
                # The only case that this else clause will be reached is at n == 0, that even at metric_iterate_crfs[-1], or final_min_crf, the predicted quality is still below the target the target.
                print(f"\033[K{metric_scene_frame_print(i, scene["start_frame"], scene["end_frame"])} / Potential low quality scene / The predicted quality at `final_min_crf` is {value:.3f}, which is worse than `metric_target` at {metric_target:.3f}")
                printing = True
                final_crf = metric_iterate_crfs[n-1]
            
            if final_crf is not None:
                break
    else:
        assert False, "This indicates a bug in the original code. Please report this to the repository including this error message in full."

    if character_enable:
        clip = character_clip[scene["start_frame"]]
        for fter in range(1, (scene["end_frame"] - scene["start_frame"]) // 8):
            clip += (character_clip[scene["start_frame"] + fter * 8])

        roi_map = []
        uniform_offset = character_sigma // 1.5
        uniform_nonboosting_offset = 0
        character_key_multiplier = 1.00
        character_32_multiplier = 0.80
        character_16_multiplier = 0.60
        character_8_multiplier = 0.40
        for fter, frame in enumerate(clip.frames(backlog=48)):
            a = np.array(frame[0], dtype=np.float32)
            a = np.round(a * -7).reshape((1, -1))

            if fter == 0:
                a = np.round(a * (character_sigma / 1.75 * character_key_multiplier) + uniform_offset)
                roi_map.append([0, a])
                roi_map.append([1, np.full_like(a, uniform_nonboosting_offset, dtype=np.float32)])
            elif fter % 4 == 0:
                a = np.round(a * (character_sigma / 1.75 * character_32_multiplier) + uniform_offset)
                roi_map.append([fter * 8, a])
                roi_map.append([fter * 8 + 1, np.full_like(a, uniform_nonboosting_offset, dtype=np.float32)])
            elif fter % 2 == 0:
                a = np.round(a * (character_sigma / 1.75 * character_16_multiplier) + uniform_offset)
                roi_map.append([fter * 8, a])
                roi_map.append([fter * 8 + 1, np.full_like(a, uniform_nonboosting_offset, dtype=np.float32)])
            else:
                a = np.round(a * (character_sigma / 1.75 * character_8_multiplier) + uniform_offset)
                roi_map.append([fter * 8, a])
                roi_map.append([fter * 8 + 1, np.full_like(a, uniform_nonboosting_offset, dtype=np.float32)])

        needed_offset = 0
        crf_offset = 0
        for line in roi_map:
            if (offset := np.max(line[1])) < 0.01:
                needed_offset = np.max([needed_offset, -offset])
        if needed_offset > 0.01:
            for line in roi_map:
                line[1] += needed_offset
            crf_offset = 0.25 * -needed_offset
               
        roi_map_file = roi_maps_dir / f"roi-map-{metric_scene_rjust(i)}.txt"
        with roi_map_file.open("w") as roi_map_f:
            for line in roi_map:
                roi_map_f.write(f"{line[0]} ")
                np.savetxt(roi_map_f, line[1], fmt="%d")

    if character_enable:
        roi_parameters_string = f"--roi-map-file '{roi_map_file}'"
        roi_parameters_array = ["--roi-map-file", str(roi_map_file)]
    else:
        roi_parameters_string = ""
        roi_parameters_array = []

    if character_enable:
        final_crf = final_crf + crf_offset

    final_crf_ = final_dynamic_crf(final_crf)
    # If you want to use a different encoder than SVT-AV1 derived ones, modify here. This is not tested and may have additional issues.
    final_crf_ = round(final_crf_ / 0.25) * 0.25

    if printing or metric_verbose or final_crf_ < metric_reporting_crf:
        print(f"\033[K{metric_scene_frame_print(i, scene["start_frame"], scene["end_frame"])} / OK / Final crf: {final_crf_:.2f}")

    if zones_file:
        # If you want to use a different encoder than SVT-AV1 derived ones, modify here. This is not tested and may have additional issues.
        zones_f.write(f"{scene["start_frame"]} {scene["end_frame"]} svt-av1 {"reset" if final_parameters_reset else ""} --crf {final_crf_:.2f} {final_dynamic_parameters(final_crf)} {final_parameters} {roi_parameters_string}\n")

    if scenes_file:
        scene["zone_overrides"] = {
            "encoder": "svt_av1",
            "passes": 1,
            "video_params": ["--crf", f"{final_crf_:.2f}" ] + final_dynamic_parameters(final_crf).split() + final_parameters.split() + roi_parameters_array,
            "photon_noise": final_photon_noise,
            "extra_splits_len": scene_detection_extra_split,
            "min_scene_len": scene_detection_min_scene_len
        }
        if final_chroma_noise_available:
            scene["zone_overrides"]["chroma_noise"] = final_chroma_noise

if zones_file:
    zones_f.close()

if scenes_file:
    with scenes_file.open("w") as scenes_f:
        json.dump(scenes, scenes_f, cls=NumpyEncoder)
print(f"\033[K{metric_scene_frame_print(i, scene["start_frame"], scene["end_frame"])} / Boost calculation complete / {(i + 1) / (time() - start):.02f} scenes per second")











































































# You don't need to modify anything here.
class UnreliableModelError(Exception):
    def __init__(self, model, message):
        super().__init__(message)
        self.model = model
# ---------------------------------------------------------------------
# For SSIMU2, by default, Progression Boost fit the metric data to a
# constrained cubic polynomial model. If a fit could not be made under
# constraints, an „Unreliable model“ will be reported. You don't need
# to modify anything here unless you want to implement your own method.
# The code here is a little bit long, try scrolling harder if you can't
# reach the next paragraph.
# def metric_model(crfs: np.ndarray[float], quantisers: np.ndarray[float]) -> Callable[[float], float]:
#     if crfs.shape[0] >= 4:
#         polynomial = lambda X, coef: coef[0] * X ** 3 + coef[1] * X ** 2 + coef[2] * X + coef[3]
#         # Mean Squared Error biased towards overboosting
#         objective = lambda coef: np.average((error := (quantisers - polynomial(crfs, coef))) ** 2, weights=metric_better_metric(0, error) + 1.0)
#         if metric_better_metric(quantisers[0] * 1.1, quantisers[0]):
#             bounds = Bounds([-np.inf, -np.inf, -np.inf, -np.inf], [0, np.inf, np.inf, np.inf])
#             constraints = [
#                 # Second derivative 6ax + 2b <= 0 if np.greater
#                 {"type": "ineq", "fun": lambda coef: -(6 * coef[0] * final_min_crf + 2 * coef[1])},
#                 # b^2 - 3ac <= 0
#                 {"type": "ineq", "fun": lambda coef: -(coef[1] ** 2 - 3 * coef[0] * coef[2])}
#             ]
#         else:
#             bounds = Bounds([0, -np.inf, -np.inf, -np.inf], [np.inf, np.inf, np.inf, np.inf])
#             constraints = [
#                 # Second derivative 6ax + 2b >= 0 if np.less
#                 {"type": "ineq", "fun": lambda coef: 6 * coef[0] * final_min_crf + 2 * coef[1]},
#                 # b^2 - 3ac <= 0
#                 {"type": "ineq", "fun": lambda coef: -(coef[1] ** 2 - 3 * coef[0] * coef[2])}
#             ]
#         fit = minimize(objective, [0, *np.polyfit(crfs, quantisers, 2)],
#                        method="SLSQP", options={"ftol": 1e-6}, bounds=bounds, constraints=constraints)
#         if fit.success and not np.isclose(fit.x[0], 0, rtol=0, atol=1e-7):
#             return partial(polynomial, coef=fit.x)
#
#     if crfs.shape[0] >= 3:
#         polynomial = lambda X, coef: coef[0] * X ** 2 + coef[1] * X + coef[2]
#         # Mean Squared Error biased towards overboosting
#         objective = lambda coef: np.average((error := (quantisers - polynomial(crfs, coef))) ** 2, weights=metric_better_metric(0, error) + 1.0)
#         if metric_better_metric(quantisers[0] * 1.1, quantisers[0]):
#             bounds = Bounds([-np.inf, -np.inf, -np.inf], [0, np.inf, np.inf])
#             # First derivative 2ax + b <= 0 if np.greater
#             constraints = [{"type": "ineq", "fun": lambda coef: -(2 * coef[0] * final_min_crf + coef[1])}]
#         else:
#             bounds = Bounds([0, -np.inf, -np.inf], [np.inf, np.inf, np.inf])
#             # First derivative 2ax + b >= 0 if np.less
#             constraints = [{"type": "ineq", "fun": lambda coef: 2 * coef[0] * final_min_crf + coef[1]}]
#         fit = minimize(objective, [0, *np.polyfit(crfs, quantisers, 1)],
#                        method="SLSQP", options={"ftol": 1e-6}, bounds=bounds, constraints=constraints)
#         if fit.success and not np.isclose(fit.x[0], 0, rtol=0, atol=1e-7):
#             return partial(polynomial, coef=fit.x)
#
#     if crfs.shape[0] >= 2:
#         polynomial = lambda X, coef: coef[0] * X + coef[1]
#         # Mean Squared Error biased towards overboosting
#         objective = lambda coef: np.average((error := (quantisers - polynomial(crfs, coef))) ** 2, weights=metric_better_metric(0, error) + 1.0)
#         if metric_better_metric(quantisers[0] * 1.1, quantisers[0]):
#             bounds = Bounds([-np.inf, -np.inf], [0, np.inf])
#         else:
#             bounds = Bounds([0, -np.inf], [np.inf, np.inf])
#         fit = minimize(objective, np.polyfit(crfs, quantisers, 1),
#                        method="L-BFGS-B", options={"ftol": 1e-6}, bounds=bounds)
#         if fit.success and not np.isclose(fit.x[0], 0, rtol=0, atol=1e-7):
#             if not crfs.shape[0] >= 3:
#                 return partial(polynomial, coef=fit.x)
#             else:
#                 def cut(crf):
#                     if crf <= np.average([crfs[-1], final_max_crf], weights=[3, 1]):
#                         return polynomial(crf, fit.x)
#                     else:
#                         return np.nan
#                 return cut
#
#     def cut(crf):
#         for i in range(0, crfs.shape[0]):
#             if crf <= crfs[i]:
#                 return quantisers[i]
#         else:
#             return np.nan
#     raise UnreliableModelError(cut, f"Unable to construct a polynomial model. This may result in overboosting.")

# For SSIMU2, Emre also suggests using PCHIP interpolator, which is
# provided here. This is not yet tested to be fully stable. Use it with
# caution.
# from scipy.interpolate import PchipInterpolator
# def metric_model(crfs: np.ndarray[float], quantisers: np.ndarray[float]) -> Callable[[float], float]:
#     return PchipInterpolator(crfs, quantisers, extrapolate=True)

# For Butteraugli 3Norm, as explained in the `testing_crfs` section,
# there appears to be a linear relation between `--crf` and Butteraugli
# 3Norm scores in `--crf [10 ~ 30]` range. For `--crf`s below 10 to 12,
# it seems like the encode quality increases faster than `--crf`
# decreases. The following function accounts for this and deviates from
# the linear regression at `--crf` 12 or lower. The rate used in the
# function is very conservative, in the sense that it will almost only
# overboost than underboost. If you're using the default `testing_crfs`
# for Butteraugli 3Norm, comment the function above for SSIMU2 and
# uncomment the function below.
def metric_model(crfs: np.ndarray[float], quantisers: np.ndarray[float]) -> Callable[[float], float]:
    polynomial = lambda X, coef: coef[0] * X + coef[1]
    # Mean Squared Error biased towards overboosting
    objective = lambda coef: np.average((error := (quantisers - polynomial(crfs, coef))) ** 2, weights=metric_better_metric(0, error) + 1.0)
    if metric_better_metric(quantisers[0] * 1.1, quantisers[0]):
        bounds = Bounds([-np.inf, -np.inf], [0, np.inf])
    else:
        bounds = Bounds([0, -np.inf], [np.inf, np.inf])
    fit = minimize(objective, np.polyfit(crfs, quantisers, 1),
                    method="L-BFGS-B", options={"ftol": 1e-6}, bounds=bounds)
    if fit.success and not np.isclose(fit.x[0], 0, rtol=0, atol=1e-7):
        def predict(crf):
            if crf >= 11:
                return polynomial(crf, fit.x)
            else:
                return polynomial(12 - (12 - crf) ** 1.12, fit.x)
        return predict

    def cut(crf):
        for i in range(0, crfs.shape[0]):
            if crf <= crfs[i]:
                return quantisers[i]
        else:
            return np.nan
    raise UnreliableModelError(cut, f"Test encodes with higher `--crf` received better score than encodes with lower `--crf`. This may result in overboosting.")

# If you want to use a different method, you can implement it here.
#
# This function receives quantisers corresponding to each test encodes
# specified previously in `testing_crfs`, which is provided in the
# first argument `crfs`. It should return a function that will return
# predicted metric score when called with `--crf`.
# You should raise an UnreliableModelError with a model and an error
# message if the model constructed is unreliable. You will have to
# return a model in the exception. If the model constructed is
# unusable, you can use something similar to the `cut` function at the
# end of the two builtin `metric_model` functions.
# def metric_model(crfs: np.ndarray[float], quantisers: np.ndarray[float]) -> Callable[[float], float]:
#     pass









# ---------------------------------------------------------------------
# The following function is run after we've measured the test encodes
# and deducted a `--crf` number for the final encode. It is used to
# perform a final adjustment to the `--crf` value in the output.
def final_dynamic_crf(crf: float) -> float:

# The first thing we want to address is the difference in quality
# difference between `--crf`s moving from faster `--preset`s in test
# encodes to slower `--preset`s in the final encode. Let's say if
# `--crf A` is 50% better than `--crf B` in `--preset 6`, it might be
# up to 80% better in `--preset -1`. To help mitigate this issue, we
# can apply a uniform offset.
# 
# The higher the difference between the test encode `--preset` and the
# final encode `--preset` is, the smaller the value you can try here.
# This is some of the numbers we found working during our tests:
# [test encode `--preset` → final encode `--preset`: offset]
# `--preset 6` → `--preset 0`: 0.84 to 0.82
# `--preset 6` → `--preset 1`: 0.88-ish
# `--preset 7` → `--preset 2`: 0.92
# `--preset 8` → `--preset 4`: 0.94
#
# Also, if you're doing multiscene encoding tests such as to test out
# optimal encoder parameters to use, you can run the metric on these
# tests and find out around which `--crf` levels does the bad frames
# commonly reside, and you can adjust this value to better suit your
# settings.
#
# Select one of the values below by uncommenting the line and
# commenting the others, or picking your own value by entering into any
# of the lines.
    crf = (crf / 24.00) ** 0.92 * 24.00
    # crf = (crf / 24.00) ** 0.88 * 24.00
    # crf = (crf / 24.00) ** 0.82 * 24.00
