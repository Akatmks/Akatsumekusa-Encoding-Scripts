<p align="center"><a href="#progression-boost">Progression Boost</a> · <a href="#dispatch-server">Dispatch Server</a> · <a href="#vapoursynth-scene-detection">VapourSynth Scene Detection</a></p>

# Progression Boost

### Introduction

Thanks to Ironclad and their grav1an, Miss Moonlight and their Lav1e, Trix and their autoboost, and BoatsMcGee and their Normal-Boost that makes this script possible.

Constant quality? Eliminating bad frames? Whatever your target is, Progression Boost gets you covered.  
Progression Boost is a flexible boosting script that runs faster and gives better result than av1an's `--target-quality`. It works in the same idea as Ironclad's grav1an using polynomial regression, and can be easily configured to target different quality targets and more.  

### Usage

As a starting point, Progression Boost offers multiple presets with different quality targets. You can choose one that's closer to what you want to achieve with your encode, and then modify the config from that.  

For users that don't want too much tinkering and just want to quickly get a good result – one that's even better than av1an's `--target-quality`, both qualitywise and timewise – don't worry. There will be guides in the file specifically for this. Once you've picked the suitable preset for your target, you would only need to adjust three quick parameters in the files and you are good to go! Download a preset and follow the guide at the very top of the file.  

| Preset | Quality Target Explained |
| :-- | :-- |
| [Butteraugli-Max](../Preset-Butteraugli-3Norm-INFNorm-Max/Progression-Boost/Progression-Boost.py) | Targeting high quality, focusing on getting even the worst frame good. |
| [Butteraugli-Root-Mean-Cube](../Preset-Butteraugli-3Norm-Root-Mean-Cube/Progression-Boost/Progression-Boost.py) | Targeting medium-high to high quality, focusing on quality consistency. |
| [SSIMU2-15th-Percentile](../master/Progression-Boost/Progression-Boost.py) | Targeting medium to high quality, focusing on reducing bad frames. |
| [SSIMU2-Harmonic-Mean](../Preset-SSIMU2-Harmonic-Mean/Progression-Boost/Progression-Boost.py) | Targeting medium to high quality, focusing on quality consistency. |
| [SSIMU2-Harmonic-Mean-<br />Dampening](../Preset-SSIMU2-Harmonic-Mean-Dampening/Progression-Boost/Progression-Boost.py) | Targeting lower quality, maintaining a baseline consistency <br />while avoiding too much bloating. |

After you've downloaded a preset, open the file in a text editor and follow the guide at the very top to adjust the config. The guide should be able to lead you through all the options for Progression Boost.  

After you've adjusted the config for the encode, you need to install a few dependencies before you run Progression Boost:  
* Progression Boost's Python dependencies are specified in [`requirements.txt`](Progression-Boost/requirements.txt) including `numpy` and `scipy`. You can install them using pip.  
* Progression Bosot by default uses lsmas as video provider, but you can always switch to BestSource or other video providers in the config.  
* Progression Boost supports all VapourSynth based metric calculation. All presets are set to use Vship by default, which can be installed from vsrepo (`vship_nvidia` or `vship_amd`) or AUR ([Cuda](https://aur.archlinux.org/packages/vapoursynth-plugin-vship-cuda-git) or [AMD](https://aur.archlinux.org/packages/vapoursynth-plugin-vship-amd-git)). However, if you can only use vszip, you can easily switch to it or any other VapourSynth based methods in the config. Search for `metric_calculate` in the file.  
* Additionally, to ensure a better quality, all presets except for Preset-SSIMU2-Harmonic-Mean-Dampening by default use WWXD or Scxvid based scene detection methods. You would need to install them from vsrepo (`wwxd`, `scxvid`) or AUR ([WWXD](https://aur.archlinux.org/packages/vapoursynth-plugin-wwxd-git), [Scxvid](https://aur.archlinux.org/packages/vapoursynth-plugin-scxvid-git)). However, if you can't get them installed. Don't worry. This is totally optional, and you can always switch to av1an based scene detection in the config.  
* If you want to test out the experimental feature character boosting, you would need to install additional dependencies vs-mlrt and akarin from vsrepo (`trt` or other suitable backend for vs-mlrt, `akarin`) or AUR ([trt](https://aur.archlinux.org/packages/vapoursynth-plugin-mlrt-trt-runtime-git) or other suitable runtime, [akarin](https://aur.archlinux.org/packages?K=vapoursynth-plugin-vsakarin)).

### Note

* This script will get updated from time to time. Always use the newest version when you start a new project if you can.  

* Progression Boost will encode the video multiple times until it can build a polynomial model. If you prefer a faster option that only encodes the video once and boost using a „magic number“, try Miss Moonlight's Lav1e or Trix's autoboost.  

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
