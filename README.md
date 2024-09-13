![](https://github.com/OALabs/research/workflows/CI/badge.svg) 
![](https://github.com/OALabs/research/workflows/GH-Pages%20Status/badge.svg) 
[![Chat](https://img.shields.io/badge/Chat-Discord-blueviolet)](https://discord.gg/UWdMC3W2qn) 
[![Support](https://img.shields.io/badge/Support-Patreon-FF424D)](https://www.patreon.com/oalabs)


[**research.openanalysis.net**](https://research.openanalysis.net)

# Research Notes

This is our research notes repository, formerly known as "Lab-Notes". We use [Jupyter Notbooks](https://jupyter.org/) for all of our notes so we can directy include code. The raw notes can be found in this repository in the [_notebooks](https://github.com/OALabs/research/tree/master/_notebooks) directory and our full blog is available online at [research.openanalysis.net](https://research.openanalysis.net).


## How To Add Notes

Adding a new note is as simple as cloning out repository and launching `juptyer-lab` from the [_notebooks](https://github.com/OALabs/research/tree/master/_notebooks) directory. You can then edit notes, or add new ones. 

The note filename must start with the date in the format `yyyy-mm-dd-` for example `2022-02-22-my_note.ipynb`.

Each note must include a special markdown cell as the first cell in the notebook. The cell contains the markdown used to generate our [blog posts](https://github.com/OALabs/research/tree/master/_posts).
```
# Blog Title
> Blog Subtitle

- toc: true 
- badges: true
- categories: [tagone,tag two]
```
The blog is generated using fastpages. Full documentation can be found on the [fastpages](https://github.com/fastai/fastpages) GitHub.


