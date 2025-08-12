⮚ [Progression Boost](#progression-boost)・[Dispatch Server](#dispatch-server)・[VapourSynth Scene Detection](#vapoursynth-scene-detection)  

# Progression Boost

## Introduction

Thanks to Ironclad and their grav1an, Miss Moonlight and their Lav1e, Trix and their Auto-Boost, and BoatsMcGee and their Normal-Boost that makes this script possible.  
Thanks to name? and MA0MA0 that helps testing and coming up with new ideas for the new version of Progression Boost.  

Constant quality? Eliminating bad frames? Better character? Better birate allocation? Whatever your target is, Progression Boost gets you covered.  
Progression Boost is a fast, safe, and featurerich boosting script. It comes with readytouse presets that you can try directly, but it can also be configured to target unique quality targets and more.  

## Download

As a starting point, Progression Boost offers multiple readytouse presets.  
For users that don't want too much tinkering and just want to quickly get a good result, you can just pick a preset depending on your target and you're ready to go. Any presets can be run directly and produce a decent result. However, you may also open the file in a text editor, and there are notes in the file guiding you to the most necessary configs to adjust, such as the encoder's encoding parameters, and your target score.  
For users that wants to fine tune the boosting, you can first download a preset that's closer to what you want to achieve, and then modify from that. After you've selected and downloaded a preset, open the file in a text editor. Inside the file, there are a very detailed and complete guide on how you can adjust the boosting.  

### Presets with Character Boost

Character Boost is the crème de la crème of anime boosting. It's almost always necessary in high quality encodes, because there is not a single other way to preserve the weak character linearts that's very common in all kinds of anime. It's even more beneficial in lower quality encodes, because when filesize is the limitation, it's very important to spend the bitrate on characters which we care more about instead of the background.  
As long as you're encoding anime, and you have at the very least an entrylevel GPU such as a GTX 1060, you should always pick a preset with Character Boost.  

Butteraugli based boosting is the primary boosting method for Progression Boost. The reason is that the whole frame score of metrics such as SSIMU2 are given based on the average quality across the frame. It's not exactly rare in extreme long shots to have characters only occupying a small percentage of the scereen while the majority of the frame is background. In this case, if the character is moving while the background is still, the characters will get encoded very poorly. Mean based metric such as SSIMU2 would often fail to pick this up and represent it in the final score. To solve this, Progression Boost's Butteraugli presets use a combination of Butteraugli 3Norm and INFNorm score to make sure to we recognised these issues and give them enough boost.  
You should always pick a Butteraugli based preset, unless you're stuck with Intel's integrated GPU (AMD is fine though), or you're performing your final encode at a very fast `--preset` and you want the boosting to be as fast as possible.  

You may noticed the two „Mean“ based presets below. They are not simple arthritic mean. They are Harmonic Mean and Root Mean Cube augmented by Min or Max respectively. They should deliver the quality consistency of a mean based method while avoiding bad frames like that of a percentile based method.  
You should prefer this modified mean over the commonly used 15th percentile method.  

| Preset | Quality Target Explained |
| :-- | :-- |
| [Character-Boost-Butteraugli-Max](../Preset-Character-Boost-Butteraugli-Max/Progression-Boost/Progression-Boost.py) | Targeting highest quality, focusing on getting even the worst frame good. |
| [Character-Boost-Butteraugli-Mean](../master/Progression-Boost/Progression-Boost.py) | Targeting entire quality range, focusing on quality consistency<br /> while also reducing bad frames. |
| [Character-Boost-SSIMU2-Mean](../Preset-Character-Boost-SSIMU2-Mean/Progression-Boost/Progression-Boost.py) | Targeting medium to low quality levels, slightly faster while delivering<br />decent quality consistency. |

There is also a preset that disables metric based boosting and solely relies on Character Boosting. This is useful when the background of the source is very complicated and would take unreasonable amount of bitrate with normal metric based boosting. In this case, we can choose to disregard the background and letting it be a little bit less faithful, but rely on Character Boost to achieve a pristine quality on characters.  

| Preset | Quality Target Explained |
| :-- | :-- |
| [Character-Boost](../Preset-Character-Boost/Progression-Boost/Progression-Boost.py) | Boosting characters, while relying on `--crf` for a basic quality consistency. |

### Presets without Character Boost

As explained above, you should always use Character Boost at all quality targets, unless you don't have a GPU equivalent to GTX 1060, or you can't set up vs-mlrt. And here are the presets without Character Boost.  

Explanation for picking between Butteraugli and SSIMU2, as well as explanation for the „Mean“ based presets below are also available in the last section. In short, you should always pick a Butteraugli based preset, unless you're performing your final encode at a very fast `--preset` and you want the boosting to be as fast as possible. And the mean based methods here deliver the quality consistency of a mean based method, while in the same time they avoid bad frames like that of a percentile based method.  

| Preset | Quality Target Explained |
| :-- | :-- |
| [Butteraugli-Max](../Preset-Butteraugli-Max/Progression-Boost/Progression-Boost.py) | Targeting highest quality, focusing on getting even the worst frame good. |
| [Butteraugli-Mean](../Preset-Butteraugli-Mean/Progression-Boost/Progression-Boost.py) | Targeting entire quality range, focusing on quality consistency<br /> while also reducing bad frames. |
| [SSIMU2-Mean](../Preset-SSIMU2-Mean/Progression-Boost/Progression-Boost.py) | Targeting medium to low quality levels, slightly faster while delivering<br />decent quality consistency. |

### Scene Detection Presets

Progression Boost has a great scene detection system. This scene detection may be beneficial over av1an's scene detection even when you're doing unboosted encoding with constant `--crf`. This preset supports mixing Progression Boost's scene detection with av1an's scene detection via Progression Boost's zoning feature. But if you want just to use Progression Boost's scene detection throughout the entire encode, you can use the easiertouse standalone [VapourSynth Scene Detection](#vapoursynth-scene-detection) script.  

| Preset | Explained |
| :-- | :-- |
| [Scene-Detection](../Preset-Scene-Detection/Progression-Boost/Progression-Boost.py) | Performing Scene Detection for fixed `--crf` encoding. |

## Dependencies

Progression Boost has very few dependencies:  
* Progression Boost is a script for av1an, and it outputs scenes.json in av1an format. You need to be using av1an to use Progression Boost.  
* Progression Boost's only hard requirement other than av1an is `numpy`. You can install them using `python -m pip install numpy`.  
* Progression Bosot by default uses lsmas as video provider, but you can easily switch to BestSource or other video providers in the file itself.  
* Progression Boost supports all VapourSynth based metric calculation and FFVship. All presets are set to use Vship by default, which can be installed from vsrepo (`vship_nvidia` or `vship_amd`) or AUR ([Cuda](https://aur.archlinux.org/packages/vapoursynth-plugin-vship-cuda-git) or [AMD](https://aur.archlinux.org/packages/vapoursynth-plugin-vship-amd-git)). Miss Moonlight spent a lot of time optimising Vship and it can even run on integrated GPU decently well.  
  However, if you don't have that luxury and can only use vszip, you can easily switch to vszip or any other VapourSynth based methods easily in the config. Search for `metric_calculate` in the file.  
  If you're using a preset that skips metric based boosting, you don't need any of these dependencies.  
* Additionally, to ensure a better quality, all presets by default use WWXD or Scxvid based scene detection methods. You would need to install them from vsrepo (`wwxd`, `scxvid`) or AUR ([WWXD](https://aur.archlinux.org/packages/vapoursynth-plugin-wwxd-git), [Scxvid](https://aur.archlinux.org/packages/vapoursynth-plugin-scxvid-git)).  
  However, if you can't get them installed. Don't worry. This is totally optional, and you can always switch to av1an based scene detection in the config.  
* At last, if you want to use Character Boost, you would need to install vs-mlrt and akarin. You can install them from vsrepo (`trt` or other suitable backend for vs-mlrt, `akarin`) or AUR ([trt](https://aur.archlinux.org/packages/vapoursynth-plugin-mlrt-trt-runtime-git) or other suitable runtime, [akarin](https://aur.archlinux.org/packages?K=vapoursynth-plugin-vsakarin)). You would also need to download the anime-segmentation model available at vs-mlrt's [release page](https://github.com/AmusementClub/vs-mlrt/releases/external-models).  
  This is also optional and you don't need these if you're not using a preset with Character Boost enabled.  

After you've set up the dependencies, you may run the file directly and it will produce a decent result. Or you can open the file in a text editor and adjust the config for your needs. For people that wants to quickly adjust, there's a note inside leading you to the most necessary configs. For the people that wants to fine tune the result, there're very detailed guides inside the file.  

## Note

* This script will get updated from time to time. Always use the newest version when you start a new project if you can.  

# Dispatch Server

### Introduction

Dispatch Server aims to solve two common problems in AV1 encoding:  

1. Since the time `--lp` stopped meaning eact number of logical processors used and started standing for „level of parallelism“, there has been a question about the best `--workers` number to use for a given `--lp`. The difficulty is that SVT-AV1-PSY can take vastly different amount of resources from scene to scene depending on the complexity of the scene, and it's almost impossible to have a number for `--workers` that would not, at some point encoding an episode, greatly overloads or underutilises the system.  
This is where the Dispatch Server comes it. It mitigates this issue by monitoring the CPU usage and only dispatching a new worker when there's free CPU available.  

2. For heavily filtered encodes, it's very easy to run into VRAM limitations as Av1an runs multiple workers in parallel. It's suboptimal to use exactly the amount of workers that would fully utilise the VRAM, because when VSPipe for a worker has finished filtering but the encoder is still yet to consume the lookahead frames, the worker is not using any VRAM. It's also not possible to use slightly more workers than the VRAM allows, because by chance sometimes VSPipe for all workers will run in the same time, and the system would likely freeze and not being able to continue.  
The Dispatch Server solves this by monitoring the VRAM usage and only dispatching a new worker when there's free VRAM available.  

### Usage

The Dispatch Server consists of three parts:  

* [`Server.py`](Dispatch-Server/Server.py): This is the main script for the Dispatch Server. All the monitoring and dispatching happen in this script.  
* [`Server-Shutdown.py`](Dispatch-Server/Server-Shutdown.py): This is the shutdown script for `Server.py`. This shutdown script can be automatically run after encoding finished.  
* [`Worker.py`](Dispatch-Server/Worker.py): The lines of codes in this script will need to be copied to the top of the filtering vpy script. It pauses the execution of the vpy script until it receives the green light from the Dispatch Server.  

To adapt the Dispatch Server:  

1. Check the [`requirements.txt`](Dispatch-Server/requirements.txt) in the folder. This `requirements.txt` can directly be used for NVIDIA GPUs. For other GPU brands, replace the `nvidia-ml-py` package in the `requirements.txt` with the appropriate package. After that, use pip to install the dependencies for the dispatch server from `requirements.txt`. Running the Dispatch Server in the same Python as the Python used for filtering is recommended.  
2. Download the [`Server.py`](Dispatch-Server/Server.py) and [`Server-Shutdown.py`](Dispatch-Server/Server-Shutdown.py). Open `Server.py` in a text editor, and at the top there will be several variables configuring the amount of VRAM and CPU usage expected for each worker, among other settings. Follow the guides in the file to adjust all the variables. For non-NVIDIA GPUs, replace `pyvnml` with appropriate monitoring tool to continue.  
3. Copy everything in [`Worker.py`](Dispatch-Server/Worker.py) and follow guide in the file to paste it into the filtering vpy script.  

To use the Dispatch Server:  

1. Run `Server.py` in the background or in a different terminal.  
2. Run Av1an using the modified filtering vpy script that includs the lines from `Workers.py`. For Av1an parameter `--workers`, set an arbitrarily large number of workers for Av1an to spawn so that the Dispatch Server will always have workers to dispatch when there's free CPU and VRAM.  
3. After encoding, either run `Server-Shutdown.py` to shutdown the server, or Crtl-C or SIGKILL the server process.  

### Note

* Windows' builtin Task Manager is not a good tool for checking CPU usage. The CPU Utility reported in Task Manager will never reach 100% on most systems, despite the CPU is already delivering all the performance it can. This is not an advertisement, but HWiNFO, a tool commonly used by PC building community, shows a different CPU Usage number, which is more aligned to what people expects.  

# VapourSynth Scene Detection

### Introduction

This is an excerpt from [Progression Boost](#progression-boost). Use this script to try out WWXD and Scxvid for av1an encoding.  

### Usage

Check the [`requirements.txt`](VapourSynth-Scene-Detection/requirements.txt). Download the [script](VapourSynth-Scene-Detection/VapourSynth-Scene-Detection.py) and run `python VapourSynth-Scene-Detection.py --help` to view the help and the guide.  

### Guide

In the grand scheme of scene detection, av1an `--sc-method standard` is the more universal option for scene detection. It has multiple unique optimisations and is tested to work well in most conditions.

However, it has one big problem: av1an often prefers to place the keyframe at the start of a series of still, unmoving frames. This preference even takes priority over placing keyframes at actual scene changes. For most works, it's common to find cuts where the character will make some movements at the very start of a cut, before they stops moving and starts talking. Using av1an, these few frames will be allocated to the previous scenes. These are a low number of frames, with movements, and after an actual scene changes, but placed at the very end of previous scene, which is why they will often be encoded horrendously. Compared to av1an, WWXD or Scxvid is more reliable in this matter, and would have less issues like this.  

A caveat is that WWXD and Scxvid struggles greatly in sections challenging for scene detection such as a continous cut, many times the length of `scene_detection_extra_split`, featuring lots of movements but no actual scenecuts, or sections with a lot of very fancy transition effects between cuts. WWXD and Scxvid will mark either too much or too few keyframes. This is largely alleviated by the additional scene detection logic in this script, but you should still prefer av1an `--sc-method standard` in sources with such sections.  
