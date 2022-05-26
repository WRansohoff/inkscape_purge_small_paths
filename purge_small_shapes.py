#!/usr/bin/env python

import math
import sys

# Linux (could also be /usr/local/... or user-defined)
#sys.path.append('/usr/share/inkscape/extensions')
# Windoze
sys.path.append('C:\\Program Files\\Inkscape\\share\\inkscape\\extensions')

import inkex
from inkex import bezier

##################################################################################################
# "Purge small shapes" Inkscape extension
# This extension is intended to clean up the small speckle artifacts which are often produced
# by automated image posterization algorithms, including Inkscape's "Trace Bitmap" options.
# These small shapes are a nuisance when you want to produce an image using some sort of CNC.
#
# We use a rough area approximation produced by subdividing bezier curves into N line segments.
# It will over- and under-estimate shape areas, but usually not by much.
# It is unlikely to work on self-intersecting paths.
##################################################################################################

debug = False

class PurgeSmallShapes(inkex.Effect):
    # Init function: argument parsing.
    def __init__(self):
        inkex.Effect.__init__(self)
        self.arg_parser.add_argument('-a', '--area', action = 'store',
            type = float, dest = 'area', default = 10.0)
        self.arg_parser.add_argument('-s', '--segments', action = 'store',
            type = int, dest = 'segments', default = 4)

    # Recursive helper function to walk the SVG node tree.
    # TODO: This could be improved to avoid duplicate processing of modified nodes
    # (and operate in parallel) by queueing nodes and then executing. But I don't have time now.
    def iterate_node(self, node):
        self.do_node(node)
        for child in node:
            self.iterate_node(child)

    # Entry point.
    def effect(self):
        svg = self.document.getroot()

        # If no paths are selected, operate on the whole design.
        if len(self.svg.selected)==0:
             self.iterate_node(self.document.getroot())
        # If one or more paths are selected, only operate on those paths.
        else:
            for id, node in self.svg.selected.items():
                self.iterate_node(node)

    # Helper function to calculate and return the area within a path.
    def get_path_area(self, path, node):
        # At a glance, the easiest way to do this looks like a list of Curves, which have 3/4
        # points required to produce a bezier tuple. So...Path->CubicSuperPath->[Move|Line|Curve]?
        # https://inkscape-extensions-guide.readthedocs.io/en/latest/inkex-modules.html#module-inkex.paths
        sp = path.to_superpath()
        curves = sp.to_segments()
        poly_pts = []
        last_pt = [0.0, 0.0]
        for c in curves:
            if c.__class__.__name__ == 'Move':
                # 'Move' command: Add point to polygon approximation.
                poly_pts.append([c.x, c.y])
                # Record current point coordinates in case the next command is a curve.
                last_pt = [c.x, c.y]
            elif c.__class__.__name__ == 'Line':
                # 'Line' command: Add point to polygon approximation.
                poly_pts.append([c.x, c.y])
                # Record current point coordinates in case the next command is a curve.
                last_pt = [c.x, c.y]
            elif c.__class__.__name__ == 'Curve':
                # 'Curve' command: Break the curve into N line segments.
                # Determine how many segments to use in the approximation of this curve.
                segs = self.options.segments
                sincr = 1/segs
                sv = sincr
                sarr = []
                for i in range(segs):
                    sarr.append(sv)
                    sv += sincr

                # Create bezier curve tuple: (last_point, last_handle2, this_handle1, this_point)
                bez = ((last_pt[0], last_pt[1]), (c.x2, c.y2), (c.x3, c.y3), (c.x4, c.y4))
                # Find approximate length of the curve, for scaling purposes.
                blen = bezier.bezierlength(bez, tolerance=0.03)
                # Interpolate N points along the bezier curve.
                for i in sarr:
                    # Convert length % to time-constant %. Tolerance depends on curve length.
                    midtime = bezier.beziertatlength(bez, l=i, tolerance=(blen/300.0))
                    # Get X,Y coordinates at the calculated time-constant.
                    midpoint = bezier.bezierpointatt(bez, midtime)
                    # Append interpolated point to polygon approximation.
                    poly_pts.append([midpoint[0], midpoint[1]])
                # Record current point coordinates in case the next command is a Curve.
                last_pt = [c.x4, c.y4]
            elif c.__class__.__name__ == 'ZoneClose':
                # This branch should never be reached, because the 'to_segments()' function
                # crashes if it encounters a ZoneClose command, and the 'do_node()' function has
                # already split the Path by 'Z/z' commands. Better safe than sorry tho.

                # 'Zone Close' command: line back to the polygon approximation's starting point.
                poly_pts.append([poly_pts[0][0], poly_pts[0][1]])
                # Record current point coordinates in case the next command is a curve.
                last_pt = [poly_pts[0][0], poly_pts[0][1]]

        # Add a closing point if not present.
        if (poly_pts[0][0] != poly_pts[-1][0]) and (poly_pts[0][1] != poly_pts[-1][1]):
            poly_pts.append([poly_pts[0][0], poly_pts[0][1]])

        # Debug: Draw the polygon approximation over the existing path for analysis.
        # (Use the 'Path -> Break Apart' menu item in Inkscape to un-group them if desired)
        if debug:
            poly_str = f'M {poly_pts[0][0]} {poly_pts[0][1]} '
            for i in poly_pts[1:]:
                poly_str += f'L {i[0]} {i[1]} '
            poly_str += f'z {str(path)} z'
            node.set('d', poly_str)

        # Find area of the approximated polygon.
        if len(poly_pts) <= 1:
            return 0.0
        a = 0.0
        prev_ind = len(poly_pts)-1
        for i in range(len(poly_pts)):
            a += (poly_pts[prev_ind][0] + poly_pts[i][0]) * \
                 (poly_pts[prev_ind][1] - poly_pts[i][1])
            prev_ind = i
        a = abs(a / 2.0)

        # Debug: Print calculated area. TODO: ...and a node or path ID? -_-
        if debug:
            inkex.utils.debug(a)

        # Return the calculated area.
        return a

    # Helper function to delete small shapes within an individual <path .../> node.
    def do_node(self, node):
        # Only process nodes with a path-data attribute.
        if node.attrib.has_key('d'):
            # Convert the node's path to absolute coordinates.
            wide_path = node.path.to_absolute()

            # Split the path into discrete shapes, if it contains stop-points.
            wp_str = str(wide_path)
            wp_str = wp_str.replace('Z', 'z')
            raw_path_strs = wp_str.split('z')
            # Paths can contain multiple stop points with no data in between: "z z z"
            # We should only process shapes that exist, so don't include empty path strings.
            path_strs = []
            for ps in raw_path_strs:
                if ps.strip():
                    path_strs.append(ps)
            raw_path_strs = []

            # Determine which shapes to keep, if any.
            keep_path_str = ''
            for path_str in path_strs:
                # Create Path object for this shape.
                path = inkex.paths.Path(path_str)
                # Get the approximate area inside of the path's curves.
                path_area = self.get_path_area(path, node)
                path = inkex.paths.Path(path_str + 'z')
                if path_area >= self.options.area:
                    keep_path_str += str(path) + ' '

            # Replace this node's path with the pruned copy, or delete it if it would be empty.
            # (In debug mode, all shapes are kept with their approximated polygons superimposed)
            if not debug:
                if keep_path_str:
                    node.set('d', keep_path_str)
                else:
                    node.getparent().remove(node)

PurgeSmallShapes().run()
