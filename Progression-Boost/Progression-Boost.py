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
from functools import partial
from itertools import islice
import json
import math
import numpy as np
from numpy.random import default_rng
import os
from pathlib import Path
import platform
from scipy.optimize import Bounds, minimize
from scipy.stats import median_abs_deviation
import subprocess
from time import time
import vapoursynth as vs
from vapoursynth import core

parser = argparse.ArgumentParser(prog="Progression Boost", epilog="For more configs, open `Progression-Boost.py` in a text editor and follow the guide at the very top")
parser.add_argument("-i", "--input", type=Path, required=True, help="Source video file")
parser.add_argument("--encode-input", type=Path, help="Source file for test encodes. Supports both video file and vpy file (Default: same as `--input`). This file is only used to perform test encodes, while scene detection will be performed using the video file specified in `--input`, and filtering before metric calculation can be set in the `Progression-Boost.py` file itself")
parser.add_argument("-o", "--output-zones", type=Path, help="Output zones file for encoding")
parser.add_argument("--output-scenes", type=Path, help="Output scenes file for encoding")
parser.add_argument("--output-roi-maps", type=Path, help="Directory for output ROI maps, relative or absolute. The paths to ROI maps are written into output scenes or zones file")
parser.add_argument("--temp", type=Path, help="Temporary folder for Progression Boost (Default: output zones or scenes file with file extension replaced by „.boost.tmp“)")
parser.add_argument("-r", "--resume", action="store_true", help="Resume from the temporary folder. By enabling this option, Progression Boost will reuse finished or unfinished testing encodes. This should be disabled should the parameters for test encode be changed")
parser.add_argument("--verbose", action="store_true", help="Progression Boost by default only reports scenes that have received big boost, or scenes that have built unexpected polynomial model. By enabling this option, all scenes will be reported")
args = parser.parse_args()
input_file = args.input
testing_input_file = args.encode_input
if testing_input_file is None:
    testing_input_file = input_file
zones_file = args.output_zones
scenes_file = args.output_scenes
roi_maps_dir = args.output_roi_maps
if not zones_file and not scenes_file:
    parser.print_usage()
    print("Progression Boost: error: at least one of the following arguments is required: -o/--output-zones, --output-scenes")
    raise SystemExit(2)
temp_dir = args.temp
if not temp_dir:
    if zones_file:
        temp_dir = zones_file.with_suffix(".boost.tmp")
    else:
        temp_dir = scenes_file.with_suffix(".boost.tmp")
temp_dir.mkdir(parents=True, exist_ok=True)
testing_resume = args.resume
metric_verbose = args.verbose


# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Before everything, the codes above are for commandline arguments.      # <<<<  Do you want a good result fast?  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# The commandline arguments are only for specifying inputs and outputs   # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# while all encoding settings need to be modified within the             # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
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
# presets. The difference is only the default value selected. Of course
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
# Progression Boost will encode the video multiple times to build a
# polynomial model in order to decide on the `--crf` used.
# Specify the `--crf` the test encodes will run at in each pass. The
# number of `--crf`s in this list also decides the number of test
# encodes to perform.
#
# For boosting using SSIMU2 metric using most of the common methods of
# estimating final `--crf`, it's very beneficial to run at least 4
# encode passes. Running 3 passes will only shorten the runtime by one
# fourth, while damaging the consistency of final encode by a huge
# margin. It shouldn't be preferred, unless the main encoding pass is
# also performed at a relatively high `--preset`.
# 
# Also, if you're wondering why the `--crf` values go so high to 50 and
# 60, the answer is that even at 50 or 60, some, especially still,
# scenes can still achieve amazing results with 85+ SSIMU2 mean.
testing_crfs = np.sort([10.00, 25.00, 40.00, 55.00])
#
# If you've had a lot of messages reporting „Frames in this scene
# receive a metric score below 15 for test encodes.“, try the follwing
# set of `testing_crfs` instead. Optionally, you should also adjust
# `final_max_crf` to around 55.00 when you're using this set of
# `testing_crfs`.
# testing_crfs = np.sort([10.00, 22.00, 34.00, 46.00])

# Boosting using Butteraugli 3Norm metric is different. During our
# testing using SVT-AV1-PSY v2.3.0-Q and v3.0.2, we observed a linear
# relation between `--crf` and Butteraugli 3Norm score in
# `--crf [10 ~ 30]` range. This is both a blessing and a curse. The
# blessing is that we can create a good linear model with only two test
# encode passes. The curse is that we're unable to build a good model
# extending to beyond `--crf 30`, which closes the door to encodes
# targeting lower quality targets. Comment the lines above and
# uncomment the lines below if you want to make a linear model for
# Butteraugli 3Norm targeting lower `--crf`s.
# testing_crfs = np.sort([12.00, 20.00])

# Please keep this list sorted and only enter `--crf` values that are
# multiples of 0.25. Progression Boost will break if this requirement
# is not followed.
# ---------------------------------------------------------------------
# Do you want to change other parameters than `--crf` dynamically
# during the test encode? This function receives a `--crf` value and
# should return a string of parameters for the encoder.
#
# If you don't want to change any parameters dynamically, leave this
# function untouched.
def testing_dynamic_parameters(crf: float) -> str:
    return ""
# ---------------------------------------------------------------------
# Specify the `--video-params` or parameters for the encoder during      # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# test encodes. You should use the same parameters as your final         # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# encode, except for `--film-grain`, which you may want to set to `0`    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# for test encode, and `--preset`, which you want to use a faster        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# preset. You need to specify everything other than `--input`,           # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# `--output`, `--crf` and the parameters you've set to generate          # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# dynamically.                                                           # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
testing_parameters = "--lp 3 --keyint -1 --input-depth 10 --preset 7 --fast-decode 1 --color-primaries 1 --transfer-characteristics 1 --matrix-coefficients 1 --color-range 0"
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Config for the target quality to generate the final `--crf` comes
# later in the config. But before that, specify a hard limit for the
# final `--crf`.
#
# Specify a `--crf` value that's not too far away from the lowest and
# the highest `--crf` value specified in `testing_crfs` to be safe.
final_min_crf = 6.00
final_max_crf = 60.00

# If you're using the default `testing_crfs` for Butteraugli 3Norm,
# comment the line above for SSIMU2 and uncomment the lines below.
# final_min_crf = 6.00
# final_max_crf = 30.00
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
# During our test, we found that 0.92 should be a safe value going from
# `--preset 7` to `--preset 2`, while 0.84 to 0.82 should be a fine
# value from `--preset 6` to `--preset 0`.
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

# Do you want a real constant quality, or do you just want a small
# boost, not wishing to throw a lot of bitrates on the most demanding
# scenes? Here's a way to dampen scenes that has been boosted to very
# high `--crf`. Enable this if needed.
#     if crf < 26.00:
#         crf = (crf / 26.00) ** 0.50 * 26.00

# You may also implement your own function here.
# The `--crf`s this function receives are in multiples of 0.05. The new
# `--crf`s it returns can be in any precision.
# Even if you change things here, do not remove `final_min_crf` and 
# `final_max_crf` from last section. They are necessary for Progression
# Boost to work, even if you apply additional limits here.
    return crf
# ---------------------------------------------------------------------
# Do you want to change other parameters than `--crf` dynamically for
# the output zones file (and the eventual final encode)? This function
# receives a `--crf` value and should return a string of parameters.
#
# An example usage is to lower `--preset` while increase `--crf` a
# little bit for scenes that are boosted to very low `--crf`. However,
# this is not tested, and whether it's worth it is not clear.
#
# If you don't want to change any parameters dynamically, leave this
# function untouched.
def final_dynamic_parameters(crf: float) -> str:
    return ""
# ---------------------------------------------------------------------
# Specify other `--video-params` or parameters for the encoder for the   # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# `--output-zones` and `--output-scenes` file. You should not specify    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# `--crf` or the parameters you've set to generate dynamically.          # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# Only for `--output-zones`, you may choose to not specifying anything   # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# here and later specifying the parameters directly to av1an. For        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# `--output-scenes`, this scenes file from Progression Boost would be    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# the final file, and all later parameters to av1an would be             # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# disregarded per design of av1an.                                       # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# You should also set `testing_parameters` above with the same           # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# parameters you use here. Read the guide above for                      # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# `testing_parameters` for the details.                                  # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
final_parameters = "--lp 3 --keyint -1 --input-depth 10 --preset 0 --color-primaries 1 --transfer-characteristics 1 --matrix-coefficients 1 --color-range 0"
# If you put all your parameters here, you can also enable this option   # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# to use the reset flag in the zones file. This only affects             # <<<<  The next variable that you have to adjust is quite low  <<<<<<
# `--output-zones` and not `--output-scenes`.                            # <<<<  down the script at somewhere around line 700 to 900.  <<<<<<<<
final_parameters_reset = False
# ---------------------------------------------------------------------
# Specify `--photon-noise` and `--chroma-noise` for the scenes file.
# You should specify this the same way these values are represented
# in each scene in the scenes JSON. This is only applied in
# `--output-scenes` and not `--output-zones`.
photon_noise = None
chroma_noise = False
# Note that due to av1an being not backward compatible, depending on     # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# the version of av1an you're using, if you see av1an complaining about  # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# extra field `chroma_noise` in the scenes file, set the following       # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# variable to `False`. If you see av1an complaining about not finding    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# the field `chroma_noise` in the scenes file, set the following         # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# variable to `True`.                                                    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
chroma_noise_available = True
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Specify the desired scene length for scene detection. The result from
# this scene detection pass will be used both for test encodes and the
# final encodes.
scene_detection_extra_split = 264
scene_detection_min_scene_len = 12
# The next setting is only used if WWXD or SCXVID via VapourSynth is
# selected as the scene detection method in the next section.
# WWXD has the tendency to flag too much scenechanges in complex
# everchanging sections. This setting marks the length for a scene for
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
scene_detection_target_split = 60
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
# a continous cut many times the length of
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
# If you want to use av1an for scene detection, specify the av1an
# parameters. You need to specify all parameters for an `--sc-only`
# pass other than `-i`, `--temp` and `--scenes`.
# scene_detection_method = "av1an".lower()
# scene_detection_parameters = f"--sc-method fast --chunk-method lsmash"
# Below are the parameters that should always be used. Regular users
# would not need to modify these.
# scene_detection_parameters += f" --sc-only --extra-split {scene_detection_extra_split} --min-scene-len {scene_detection_min_scene_len}"

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
# such as a continous cut many times the length of
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
# are no sections difficult for scene detection, WWXD or Scxvid is
# preferred over `--sc-method fast`. If there are such sections, as
# explained above when introducing av1an-based scene detection,
# `--sc-method standard` should be preferred.
# 
# Progression Boost provides two options for VapourSynth-based scene
# detection, `wwxd` and `wwxd_scxvid`. `wwxd_scxvid` is slightly safer
# than `wwxd` alone, but multiple times slower. You should use
# `wwxd_scxvid` unless it's too slow, which `wwxd` can be then used. If
# you want to use VapourSynth-based scene detection, comment the lines
# above for av1an, uncomment the first line below for VapourSynth, and
# then uncomment the specific method you want to use for scene
# detection.
#
# Note that if you're encoding videos with full instead of limited
# colour range, you must go down to the code and adjust the threshold.
# Search for „limited“, and there will be a comment there marking how
# you should adjust.
scene_detection_method = "vapoursynth".lower()
# scene_detection_vapoursynth_method = "wwxd_scxvid".lower() # Preferred
scene_detection_vapoursynth_method = "wwxd".lower() # Fast
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Specify the av1an parameters for the test encodes. You need to
# specify everything other than `-i`, `-o`, `--temp`, `--resume`,
# `--video-params`, and `--scenes`.
#
# Make sure the number of workers set here suits the number of `--lp`
# specified in `testing_parameters`. As a reference, per BONES and my
# testing, for SVT-AV1-PSY v2.3.0-B, it's optimum to use `--lp 3` and
# `--workers 8` for system with 32 threads, and `--lp 3` and
# `--workers 6` for system with 24 threads.
testing_av1an_parameters = "--workers 8 --chunk-method lsmash --pix-format yuv420p10le --encoder svt-av1 --concat mkvmerge"
# Below are the parameters that should always be used. Regular users
# would not need to modify these.
testing_av1an_parameters += " -y"
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Once the test encodes finish, Progression Boost will start
# calculating metric for each scenes.
# If you want to do some filtering before calculating, you can modify
# the following lines. Otherwise you can leave it unchanged.
metric_reference = core.lsmas.LWLibavSource(input_file.expanduser().resolve(), cachefile=temp_dir.joinpath("source.lwi").expanduser().resolve())
# ---------------------------------------------------------------------
# Additionally, you can also apply some filters to both the source and
# the encoded clip before calculating metric. By default, no processing
# is performed.
def metric_process(clips: list[vs.VideoNode]) -> list[vs.VideoNode]:
    return clips

# If you want higher speed calculating metrics, here is a hack. What
# about cropping the clip from 1080p to 900p or 720p? This is tested to
# have been working very well, producing very similar final `--crf`s
# while increasing measuring speed significantly. However, since we
# are cropping away outer edges of the screen, for most anime, we will
# have proportionally more characters than backgrounds in the cropped
# compare. This may not may not be preferrable. If you want to enable
# cropping, comment the lines above and uncomment the lines below to
# crop the clip to 900p before comparing.
# def metric_process(clips: list[vs.VideoNode]) -> list[vs.VideoNode]:
#     for i in range(len(clips)):
#         clips[i] = clips[i].std.Crop(left=160, right=160, top=90, bottom=90)
#     return clips
# ---------------------------------------------------------------------
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
metric_highest_diff_frames = 6
# We will avoid selecting frames too close to each other to avoid
# picking all the frames from, let's say, a fade at the start or the
# end of the scene.
metric_highest_diff_min_separation = 10
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
metric_upper_diff_bracket_frames = 4
metric_lower_diff_bracket_frames = 4
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
metric_upper_diff_bracket_fallback_frames = metric_upper_diff_bracket_frames // 2
#
# All these diff sorting and selection excludes the first frame of the
# scene since the diff data of the first frame is compared against the
# last frame from the previous scene and is irrelevant. In addition,
# the first frame as the keyframe often has great quality. Do you want
# to always include the first frame in metric calculation?
metric_first_frame = 0
#
# Sometimes, certain version of SVT-AV1-PSY will encode the last frame
# of a scene slightly worse than the rest of the frames. Do you want to
# always include the first frame in metric calculation?
metric_last_frame = 1
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# What metric do you want to use? Are you hipping, or are you zipping?
# 
# To use SSIMU2 via vship, uncomment the lines below. 
metric_calculate = core.vship.SSIMULACRA2
metric_metric = lambda frame: frame.props["_SSIMULACRA2"]
metric_better_metric = np.greater

# To use Butteraugli 3Norm via vship, uncomment the lines below.
# metric_calculate = core.vship.BUTTERAUGLI
# metric_metric = lambda frame: frame.props["_BUTTERAUGLI_3Norm"]
# metric_better_metric = np.less

# To use Butteraugli INFNorm via vship, uncomment the lines below.
# metric_calculate = core.vship.BUTTERAUGLI
# metric_metric = lambda frame: frame.props["_BUTTERAUGLI_INFNorm"]
# metric_better_metric = np.less

# During testing, we found that Butteraugli 3Norm with a tiny spice of
# Butteraugli INFNorm performs very well when targeting high quality
# targets. Butteraugli 3Norm ensures a good baseline measurement, while
# the tiny spice of Butteraugli INFNorm patches some of the small
# issues Butteraugli 3Norm missed.
# metric_calculate = core.vship.BUTTERAUGLI
# metric_metric = lambda frame: frame.props["_BUTTERAUGLI_3Norm"] * 0.97 + frame.props["_BUTTERAUGLI_INFNorm"] * 0.03
# metric_better_metric = np.less

# To use SSIMU2 via vszip, uncomment the lines below.
# metric_calculate = partial(core.vszip.Metrics, mode=0)
# metric_metric = lambda frame: frame.props["_SSIMULACRA2"]
# metric_better_metric = np.greater
# ---------------------------------------------------------------------
# You don't need to modify anything here.
class UnreliableSummarisationError(Exception):
    def __init__(self, score, message):
        super().__init__(message)
        self.score = score
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
#
# Specify the `metric_percentile` you want to observe below depending on
# your desired quality for the encode.
metric_percentile = 15
def metric_summarise(scores: np.ndarray[float]) -> float:
    return np.percentile(scores, metric_percentile, method="median_unbiased")

# The percentile method is also tested on Butteraugli 3Norm score, use
# 90th percentile instead of 10th, and 80th percentile instead of 20th,
# and you are good to go.
# metric_percentile = 90
# def metric_summarise(scores: np.ndarray[float]) -> float:
#     return np.percentile(scores, metric_percentile, method="median_unbiased")

# The second method is even more aggressive than the first method, to
# take the minimum or the maximum value from all the frames measured.
# This is the default for the preset targeting the highest quality,
# Preset-Butteraugli-3Norm-INFNorm-Max.
# A note is that if you want to get the best quality, you should also
# increase the number of frames to measured specified above in order to
# prevent random bad frames from slipping through.
# def metric_summarise(scores: np.ndarray[float]) -> float:
#     return np.min(scores)
# def metric_summarise(scores: np.ndarray[float]) -> float:
#     return np.max(scores)

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
# def metric_summarise(scores: np.ndarray[float]) -> float:
#     if np.any((small := scores < 15)):
#         scores[small] = 15
#         raise UnreliableSummarisationError(scores.shape[0] / np.sum(1 / scores), f"Frames in this scene receive a metric score below 15 for test encodes. If this happens a lot for the this specific source, try switching to better `--crf`s in `testing_crfs`.")
#     else:
#         return scores.shape[0] / np.sum(1 / scores)

# For Butteraugli 3Norm score, root mean cube is suggested by Miss
# Moonlight and tested to have good overall boosting result.
#
# To use the root mean cube method, comment the lines above for the
# percentile method, and uncomment the two lines below.
# def metric_summarise(scores: np.ndarray[float]) -> float:
#     return np.mean(scores ** 3) ** (1 / 3)

# If you want to use a different method than above to summarise the
# data, implement your own method here.
# 
# This function is called independently for every scene for every test
# encode.
# def metric_summarise(scores: np.ndarray[float]) -> float:
#     pass
# ---------------------------------------------------------------------
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
def metric_model(crfs: np.ndarray[float], quantisers: np.ndarray[float]) -> Callable[[float], float]:
    if crfs.shape[0] >= 4:
        polynomial = lambda X, coef: coef[0] * X ** 3 + coef[1] * X ** 2 + coef[2] * X + coef[3]
        # Mean Squared Error biased towards overboosting
        objective = lambda coef: np.average((error := (quantisers - polynomial(crfs, coef))) ** 2, weights=metric_better_metric(0, error) + 1.0)
        if metric_better_metric(quantisers[0] * 1.1, quantisers[0]):
            bounds = Bounds([-np.inf, -np.inf, -np.inf, -np.inf], [0, np.inf, np.inf, np.inf])
            constraints = [
                # Second derivative 6ax + 2b <= 0 if np.greater
                {"type": "ineq", "fun": lambda coef: -(6 * coef[0] * final_min_crf + 2 * coef[1])},
                # b^2 - 3ac <= 0
                {"type": "ineq", "fun": lambda coef: -(coef[1] ** 2 - 3 * coef[0] * coef[2])}
            ]
        else:
            bounds = Bounds([0, -np.inf, -np.inf, -np.inf], [np.inf, np.inf, np.inf, np.inf])
            constraints = [
                # Second derivative 6ax + 2b >= 0 if np.less
                {"type": "ineq", "fun": lambda coef: 6 * coef[0] * final_min_crf + 2 * coef[1]},
                # b^2 - 3ac <= 0
                {"type": "ineq", "fun": lambda coef: -(coef[1] ** 2 - 3 * coef[0] * coef[2])}
            ]
        fit = minimize(objective, [0, *np.polyfit(crfs, quantisers, 2)],
                       method="SLSQP", options={"ftol": 1e-6}, bounds=bounds, constraints=constraints)
        if fit.success and not np.isclose(fit.x[0], 0, rtol=0, atol=1e-7):
            return partial(polynomial, coef=fit.x)

    if crfs.shape[0] >= 3:
        polynomial = lambda X, coef: coef[0] * X ** 2 + coef[1] * X + coef[2]
        # Mean Squared Error biased towards overboosting
        objective = lambda coef: np.average((error := (quantisers - polynomial(crfs, coef))) ** 2, weights=metric_better_metric(0, error) + 1.0)
        if metric_better_metric(quantisers[0] * 1.1, quantisers[0]):
            bounds = Bounds([-np.inf, -np.inf, -np.inf], [0, np.inf, np.inf])
            # First derivative 2ax + b <= 0 if np.greater
            constraints = [{"type": "ineq", "fun": lambda coef: -(2 * coef[0] * final_min_crf + coef[1])}]
        else:
            bounds = Bounds([0, -np.inf, -np.inf], [np.inf, np.inf, np.inf])
            # First derivative 2ax + b >= 0 if np.less
            constraints = [{"type": "ineq", "fun": lambda coef: 2 * coef[0] * final_min_crf + coef[1]}]
        fit = minimize(objective, [0, *np.polyfit(crfs, quantisers, 1)],
                       method="SLSQP", options={"ftol": 1e-6}, bounds=bounds, constraints=constraints)
        if fit.success and not np.isclose(fit.x[0], 0, rtol=0, atol=1e-7):
            return partial(polynomial, coef=fit.x)

    if crfs.shape[0] >= 2:
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
            if not crfs.shape[0] >= 3:
                return partial(polynomial, coef=fit.x)
            else:
                def cut(crf):
                    if crf <= np.average([crfs[-1], final_max_crf], weights=[3, 1]):
                        return polynomial(crf, fit.x)
                    else:
                        return np.nan
                return cut

    def cut(crf):
        for i in range(0, crfs.shape[0]):
            if crf <= crfs[i]:
                return quantisers[i]
        else:
            return np.nan
    raise UnreliableModelError(cut, f"Unable to construct a polynomial model. This may result in overboosting.")

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
# def metric_model(crfs: np.ndarray[float], quantisers: np.ndarray[float]) -> Callable[[float], float]:
#     polynomial = lambda X, coef: coef[0] * X + coef[1]
#     # Mean Squared Error biased towards overboosting
#     objective = lambda coef: np.average((error := (quantisers - polynomial(crfs, coef))) ** 2, weights=metric_better_metric(0, error) + 1.0)
#     if metric_better_metric(quantisers[0] * 1.1, quantisers[0]):
#         bounds = Bounds([-np.inf, -np.inf], [0, np.inf])
#     else:
#         bounds = Bounds([0, -np.inf], [np.inf, np.inf])
#     fit = minimize(objective, np.polyfit(crfs, quantisers, 1),
#                     method="L-BFGS-B", options={"ftol": 1e-6}, bounds=bounds)
#     if fit.success and not np.isclose(fit.x[0], 0, rtol=0, atol=1e-7):
#         def predict(crf):
#             if crf >= 11:
#                 return polynomial(crf, fit.x)
#             else:
#                 return polynomial(12 - (12 - crf) ** 1.12, fit.x)
#         return predict
# 
#     def cut(crf):
#         for i in range(0, crfs.shape[0]):
#             if crf <= crfs[i]:
#                 return quantisers[i]
#         else:
#             return np.nan
#     raise UnreliableModelError(cut, f"Test encodes with higher `--crf` received better score than encodes with lower `--crf`. This may result in overboosting.")

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
metric_target = 83.000
#
# You can also have a look at `final_dynamic_crf` section, where we
# perform a flat readjustment to make the result more suitable for the
# final `--crf`.
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Character boosting is a separate boosting system based on ROI (Region
# Of Interest) map instead of `--crf`. This utilises image segmentation
# model to recognise the character in the scene, and selectively boost
# the characters.
# This feature is still in early stage of testing. Nothing really bad
# will spill out from this, just that we haven't figured out the
# perfect parameters. Head down to the code section and adjust
# parameters if necessary.
# Enable character boosting by setting the line below to True.
character_enable = False
# Set how aggressive character boosting should be.
character_sigma = 6.00
# ---------------------------------------------------------------------
if character_enable:
    import vsmlrt
# Select backend for vs-mlrt image segmentation model:
    character_backend = vsmlrt.Backend.TRT
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------


if character_enable:
    if not roi_maps_dir:
        parser.print_usage()
        print("Progression Boost: error: the following arguments is required: --output-roi-maps")
        raise SystemExit(2)
    roi_maps_dir.mkdir(exist_ok=True)

    character_model = Path(vsmlrt.models_path) / "anime-segmentation" / "isnet_is.onnx"
    if not character_model.exists():
        print(f"Progression Boost: error: Could not find anime-segmentation model at \"{character_model}\". Acquire it from https://github.com/AmusementClub/vs-mlrt/releases/external-models")


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


if platform.system() == "Windows":
    os.system("")

# Scene dectection
scene_detection_scenes_file = temp_dir.joinpath("scenes-detection.scenes.json")
scene_detection_diffs_file = temp_dir.joinpath("scenes-detection.diff.txt")

if scene_detection_method == "av1an":
    scene_detection_process = None
    if not testing_resume or not scene_detection_scenes_file.exists():
        scene_detection_scenes_file.unlink(missing_ok=True)
        command = [
            "av1an",
            "--temp", str(temp_dir.joinpath("scenes-detection.tmp")),
            "-i", str(input_file),
            "--scenes", str(scene_detection_scenes_file),
            *scene_detection_parameters.split()
        ]
        scene_detection_process = subprocess.Popen(command, text=True)

    if not testing_resume or not scene_detection_diffs_file.exists():
        scene_detection_clip = core.lsmas.LWLibavSource(input_file.expanduser().resolve(), cachefile=temp_dir.joinpath("source.lwi").expanduser().resolve())
        scene_detection_bits = scene_detection_clip.format.bits_per_sample
        scene_detection_clip = scene_detection_clip.std.PlaneStats(scene_detection_clip[0] + scene_detection_clip, plane=0, prop="Luma")
        
        start = time() - 0.000001
        scene_detection_diffs = np.empty((scene_detection_clip.num_frames,), dtype=float)
        for current_frame, frame in enumerate(scene_detection_clip.frames(backlog=48)):
            print(f"\r\033[KFrame {current_frame} / Calculating frame diff / {current_frame / (time() - start):.02f} fps", end="\r")
            scene_detection_diffs[current_frame] = frame.props["LumaDiff"]
        print(f"\r\033[KFrame {current_frame + 1} / Frame diff calculation complete / {(current_frame + 1) / (time() - start):.02f} fps")

        np.savetxt(scene_detection_diffs_file, scene_detection_diffs, fmt="%.9f")
    else:
        scene_detection_diffs = np.loadtxt(scene_detection_diffs_file)

    if scene_detection_process is not None:
        scene_detection_process.wait()
        if scene_detection_process.returncode != 0:
            raise subprocess.CalledProcessError

        assert scene_detection_scenes_file.exists()

    with scene_detection_scenes_file.open("r") as scenes_f:
        scenes = json.load(scenes_f)

elif scene_detection_method == "vapoursynth":
    if not testing_resume or not scene_detection_scenes_file.exists() or not scene_detection_diffs_file.exists():
        assert scene_detection_extra_split >= scene_detection_min_scene_len * 2, "`scene_detection_method` `vapoursynth` does not support `scene_detection_extra_split` to be smaller than 2 times `scene_detection_min_scene_len`."
    
        scene_detection_clip = core.lsmas.LWLibavSource(input_file.expanduser().resolve(), cachefile=temp_dir.joinpath("source.lwi").expanduser().resolve())
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
            
        scene_detection_rjust_digits = math.floor(np.log10(scene_detection_clip.num_frames))
        scene_detection_rjust = lambda frame: str(frame).rjust(scene_detection_rjust_digits)
        
        scenes = {}
        scenes["frames"] = scene_detection_clip.num_frames
        scenes["scenes"] = []

        diffs = np.empty((scene_detection_clip.num_frames,), dtype=float)
        diffs[0] = 1.0
        scene_detection_diffs = np.empty((scene_detection_clip.num_frames,), dtype=float)
        scene_detection_diffs[0] = 1.0
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
            # Modify here to 251.125 and 3.875 if your source has full instead of limited colour range
            luma_scenecut = frame.props["LumaMin"] > 231.125 * 2 ** (scene_detection_bits - 8) or \
                            frame.props["LumaMax"] < 19.875 * 2 ** (scene_detection_bits - 8)

            if luma_scenecut and not luma_scenecut_prev:
                diffs[current_frame] = frame.props["LumaDiff"] + 2.0
            else:
                diffs[current_frame] = frame.props["LumaDiff"] + scene_detection_scenecut
            scene_detection_diffs[current_frame] = frame.props["LumaDiff"]
                
            luma_scenecut_prev = luma_scenecut
        print(f"\033[KFrame {current_frame + 1} / Scene detection complete / {(current_frame + 1) / (time() - start):.02f} fps")

        great_diffs = diffs.copy()
        great_diffs[great_diffs < 1.0] = 0
        start_frames = scene_detection_split_scene(great_diffs, diffs, 0, len(diffs)) + [scene_detection_clip.num_frames]
        for i in range(len(start_frames) - 1):
            scenes["scenes"].append({"start_frame": int(start_frames[i]), "end_frame": int(start_frames[i + 1]), "zone_overrides": None})
        print(f"\033[KFrame [{scene_detection_rjust(start_frames[i])}:{scene_detection_rjust(start_frames[i + 1])}] / Scene creation complete")
    
        with scene_detection_scenes_file.open("w") as scenes_f:
            json.dump(scenes, scenes_f)
        np.savetxt(scene_detection_diffs_file, scene_detection_diffs, fmt="%.9f")

    else:
        with scene_detection_scenes_file.open("r") as scenes_f:
            scenes = json.load(scenes_f)
        scene_detection_diffs = np.loadtxt(scene_detection_diffs_file)

else:
    assert False, "Invalid `scene_detection_method`."
    

# Testing
for n, crf in enumerate(testing_crfs):
    if not testing_resume or not temp_dir.joinpath(f"test-encode-{n:0>2}.mkv").exists():
        # If you want to use a different encoder than SVT-AV1 derived ones, modify here. This is not tested and may have additional issues.
        command = [
            "av1an",
            "--temp", str(temp_dir.joinpath(f"test-encode-{n:0>2}.tmp")),
            "--keep"
        ]
        if testing_resume:
            command += ["--resume"]
        command += [
            "-i", str(testing_input_file),
            "-o", str(temp_dir.joinpath(f"test-encode-{n:0>2}.mkv")),
            "--scenes", str(scene_detection_scenes_file),
            *testing_av1an_parameters.split(),
            "--video-params", f"--crf {crf:.2f} {testing_dynamic_parameters(crf)} {testing_parameters}"
        ]
        subprocess.run(command, text=True, check=True)
        assert temp_dir.joinpath(f"test-encode-{n:0>2}.mkv").exists()

        temp_dir.joinpath(f"test-encode-{n:0>2}.lwi").unlink(missing_ok=True)


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
    character_clip = core.lsmas.LWLibavSource(input_file.expanduser().resolve(), cachefile=temp_dir.joinpath("source.lwi").expanduser().resolve())

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
        for fter in range(1, (scene["end_frame"] - scene["start_frame"]) // 8 + 1):
            clip += (character_clip[scene["start_frame"] + fter * 8])

        roi_map = []
        uniform_offset = character_sigma // 1.5
        uniform_nonboosting_offset = 0
        character_key_multiplier = 1.00
        character_32_multiplier = 0.80
        character_16_multiplier = 0.60
        character_8_multiplier = 0.40
        for fter, frame in enumerate(clip.frames(backlog=48)):
            a = np.array(frame[0], dtype=np.float32).reshape((character_block_height, -1))
            a = a[:, :character_block_width]
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
            "photon_noise": photon_noise,
            "extra_splits_len": scene_detection_extra_split,
            "min_scene_len": scene_detection_min_scene_len
        }
        if chroma_noise_available:
            scene["zone_overrides"]["chroma_noise"] = chroma_noise

if zones_file:
    zones_f.close()

if scenes_file:
    with scenes_file.open("w") as scenes_f:
        json.dump(scenes, scenes_f)
print(f"\033[K{metric_scene_frame_print(i, scene["start_frame"], scene["end_frame"])} / Boost calculation complete / {(i + 1) / (time() - start):.02f} scenes per second")
