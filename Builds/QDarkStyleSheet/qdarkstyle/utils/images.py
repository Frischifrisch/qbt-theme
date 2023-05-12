#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilities to process and convert svg images to png using palette colors.
"""

# Standard library imports
from __future__ import absolute_import, division, print_function

import logging
import os
import re
import tempfile

# Third party imports
from qtpy.QtCore import QSize
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QApplication

# Local imports
from qdarkstyle import (IMAGES_PATH, STYLES_SCSS_FILEPATH, QRC_FILEPATH, RC_PATH,
                        SVG_PATH)
from qdarkstyle.palette import DarkPalette

IMAGE_BLACKLIST = ['base_palette']

TEMPLATE_QRC_HEADER = '''
<RCC warning="File created programmatically. All changes made in this file will be lost!">
  <qresource prefix="{resource_prefix}">
'''

TEMPLATE_QRC_FILE = '    <file>rc/{fname}</file>'

TEMPLATE_QRC_FOOTER = '''
  </qresource>
  <qresource prefix="{style_prefix}">
      <file>style.qss</file>
  </qresource>
</RCC>
'''

_logger = logging.getLogger(__name__)


def _get_file_color_map(fname, palette):
    """
    Return map of files (i.e states) to color from given palette.
    """
    color_disabled = palette.COLOR_BACKGROUND_NORMAL
    color_focus = palette.COLOR_SELECTION_LIGHT
    color_pressed = palette.COLOR_SELECTION_NORMAL
    color_normal = palette.COLOR_FOREGROUND_DARK

    name, ext = fname.split('.')

    files_map = {
        fname: {
            fname: color_normal,
            f'{name}_disabled.{ext}': color_disabled,
            f'{name}_focus.{ext}': color_focus,
            f'{name}_pressed.{ext}': color_pressed,
        }
    }

    for f, file_colors in files_map.items():
        if f == fname:
            break

    assert file_colors

    return file_colors


def _create_colored_svg(svg_path, temp_svg_path, color):
    """
    Replace base svg with fill color.
    """
    with open(svg_path, 'r') as fh:
        data = fh.read()

    base_color = '#ff0000'  # Hardcoded in base svg files
    new_data = data.replace(base_color, color)

    with open(temp_svg_path, 'w') as fh:
        fh.write(new_data)


def convert_svg_to_png(svg_path, png_path, height, width):
    """
    Convert svg files to png files using Qt.
    """
    size = QSize(height, width)
    icon = QIcon(svg_path)
    pixmap = icon.pixmap(size)
    img = pixmap.toImage()
    img.save(png_path)


def create_palette_image(base_svg_path=SVG_PATH, path=IMAGES_PATH,
                         palette=DarkPalette):
    """
    Create palette image svg and png image on specified path.
    """
    # Needed to use QPixmap
    _ = QApplication([])

    base_palette_svg_path = os.path.join(base_svg_path, 'base_palette.svg')
    palette_svg_path = os.path.join(path, 'palette.svg')
    palette_png_path = os.path.join(path, 'palette.png')

    _logger.info("Creating palette image ...")
    _logger.info(f"Base SVG: {base_palette_svg_path}")
    _logger.info(f"To SVG: {palette_svg_path}")
    _logger.info(f"To PNG: {palette_png_path}")

    with open(base_palette_svg_path, 'r') as fh:
        data = fh.read()

    color_palette = palette.color_palette()

    for color_name, color_value in color_palette.items():
        data = data.replace('{{ ' + color_name + ' }}', color_value.lower())

    with open(palette_svg_path, 'w+') as fh:
        fh.write(data)

    convert_svg_to_png(palette_svg_path, palette_png_path, 4000, 4000)

    return palette_svg_path, palette_png_path


def create_images(base_svg_path=SVG_PATH, rc_path=RC_PATH,
                  palette=DarkPalette):
    """Create resources `rc` png image files from base svg files and palette.

    Search all SVG files in `base_svg_path` excluding IMAGE_BLACKLIST,
    change its colors using `palette` creating temporary SVG files, for each
    state generating PNG images for each size `heights`.

    Args:
        base_svg_path (str, optional): [description]. Defaults to SVG_PATH.
        rc_path (str, optional): [description]. Defaults to RC_PATH.
        palette (DarkPalette, optional): Palette . Defaults to DarkPalette.
    """

    # Needed to use QPixmap
    _ = QApplication([])

    temp_dir = tempfile.mkdtemp()
    svg_fnames = [f for f in os.listdir(base_svg_path) if f.endswith('.svg')]
    base_height = 32

    # See: https://doc.qt.io/qt-5/scalability.html
    heights = {
        32: '.png',
        64: '@2x.png',
    }

    _logger.info("Creating images ...")
    _logger.info(f"SVG folder: {base_svg_path}")
    _logger.info(f"TMP folder: {temp_dir}")
    _logger.info(f"PNG folder: {rc_path}")

    num_svg = len(svg_fnames)
    num_png = 0
    num_ignored = 0

    # Get rc links from scss to check matches
    rc_list = get_rc_links_from_scss()
    num_rc_list = len(rc_list)

    for height, ext in heights.items():
        width = height

        _logger.debug(f" Size HxW (px): {height} X {width}")

        for svg_fname in svg_fnames:
            svg_name = svg_fname.split('.')[0]

            # Skip blacklist
            if svg_name not in IMAGE_BLACKLIST:
                svg_path = os.path.join(base_svg_path, svg_fname)
                color_files = _get_file_color_map(svg_fname, palette=palette)

                _logger.debug(f"  Working on: {os.path.basename(svg_fname)}")

                # Replace colors and create all file for different states
                for color_svg_name, color in color_files.items():
                    temp_svg_path = os.path.join(temp_dir, color_svg_name)
                    _create_colored_svg(svg_path, temp_svg_path, color)

                    png_fname = color_svg_name.replace('.svg', ext)
                    png_path = os.path.join(rc_path, png_fname)
                    convert_svg_to_png(temp_svg_path, png_path, height, width)
                    num_png += 1
                    _logger.debug(f"   Creating: {os.path.basename(png_fname)}")

                    # Check if the rc_name is in the rc_list from scss
                    # only for the base size
                    if height == base_height:
                        rc_base = os.path.basename(rc_path)
                        png_base = os.path.basename(png_fname)
                        rc_name = f'/{os.path.join(rc_base, png_base)}'
                        try:
                            rc_list.remove(rc_name)
                        except ValueError:
                            pass
            else:
                num_ignored += 1
                _logger.debug(f"  Ignored blacklist: {os.path.basename(svg_fname)}")

    _logger.info(f"# SVG files: {num_svg}")
    _logger.info(f"# SVG ignored: {num_ignored}")
    _logger.info(f"# PNG files: {num_png}")
    _logger.info(f"# RC links: {num_rc_list}")
    _logger.info(f"# RC links not in RC: {len(rc_list)}")
    _logger.info(f"RC links not in RC: {rc_list}")


def generate_qrc_file(resource_prefix='qss_icons', style_prefix='qdarkstyle'):
    """
    Generate the QRC file programmaticaly.

    Search all RC folder for PNG images and create a QRC file.

    Args:
        resource_prefix (str, optional): Prefix used in resources.
            Defaults to 'qss_icons'.
        style_prefix (str, optional): Prefix used to this style.
            Defaults to 'qdarkstyle'.
    """

    _logger.info("Generating QRC file ...")
    _logger.info(f"Resource prefix: {resource_prefix}")
    _logger.info(f"Style prefix: {style_prefix}")

    _logger.info(f"Searching in: {RC_PATH}")

    files = [
        TEMPLATE_QRC_FILE.format(fname=fname)
        for fname in sorted(os.listdir(RC_PATH))
    ]
    # Join parts
    qrc_content = (TEMPLATE_QRC_HEADER.format(resource_prefix=resource_prefix)
                   + '\n'.join(files)
                   + TEMPLATE_QRC_FOOTER.format(style_prefix=style_prefix))

    _logger.info(f"Writing in: {QRC_FILEPATH}")

    # Write qrc file
    with open(QRC_FILEPATH, 'w') as fh:
        fh.write(qrc_content)


def get_rc_links_from_scss(pattern=r"\/.*\.png"):
    """
    Get all rc links from scss file returning the list of unique links.

    Args:
        pattern (str): regex pattern to find the links.

    Returns:
        list(str): list of unique links found.
    """

    with open(STYLES_SCSS_FILEPATH, 'r') as fh:
        data = fh.read()

    lines = data.split("\n")
    compiled_exp = re.compile(f'({pattern})')

    rc_list = []

    for line in lines:
        if match := re.search(compiled_exp, line):
            rc_list.append(match[1])

    return list(set(rc_list))
