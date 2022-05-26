# "Purge Small Shapes" Inkscape Extension

Have you ever run a raster image through a posterization algorithm, and felt like the vector output contained too much noise along color or brightness gradients?

If so, I feel your pain. This repository contains an Inkscape extension which aims to remove small shapes from vector images.

It works by calculating the areas of polygon approximations for each shape's bezier curves. You can choose how many line segments each curve should be split into: higher values will result in better accuracy at the expense of a longer runtime.

If you set the `debug` flag at the top of the extension script to `True`, it will draw the polygon approximations over each shape and display a list of calculated areas without deleting anything.

The `tolerance` values in the `bezier.*` function calls could be lowered to further improve accuracy, but the performance impact is significant. Reduce them at your own risk.

# Usage

To install this extension, simply copy the `.py` and `.inx` files into your extensions directory. You can find this directory in the "System" menu of Inkscape's "Edit -> Preferences" dialog. It will be listed next to a "User Extensions:" label. Restart Inkscape after copying the files, if it was running.

To use the extension, select the "Extensions -> Modify Path -> Purge Small Shapes" menu item in Inkscape.

If no paths are selected, the extension will operate on the whole document. Otherwise, it will operate on selected paths.

# Known Bugs

* Many paths will get processed twice, because the recursive node-finding function picks up on 'new' modified nodes. Even if no shapes are deleted from a node, the algorithm will replace any 'Z' closepath commands with functionally-equivalent 'z's, and a new Path object may be generated.

* The area calculation algorithm will probably fail on self-intersecting paths, resulting in false positives or negatives for such shapes.
