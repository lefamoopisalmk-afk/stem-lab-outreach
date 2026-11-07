"""Render the whole 5:00 loop (frames 0 to 7199, 7200 frames at 24 fps) to a PNG sequence.
Frames already on disk are skipped, so an interrupted render can simply be run again.
Run: blender -b loop.blend --python-exit-code 1 -P render_preview.py -- <png_folder> [first] [last]
Then: ffmpeg -framerate 24 -i <png_folder>/f%04d.png -c:v libx264 -crf 23 -pix_fmt yuv420p -movflags +faststart preview.mp4
"""
import bpy, os, sys

args = sys.argv[sys.argv.index("--") + 1:]
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.eevee.taa_render_samples = 16          # looks the same on flat colours (58 dB) and renders about 2x faster
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGB'
sc.render.image_settings.compression = 15
sc.render.use_overwrite = False
sc.render.filepath = os.path.join(args[0], "f")
if len(args) == 3:
    sc.frame_start, sc.frame_end = int(args[1]), int(args[2])
bpy.ops.render.render(animation=True)
print("RESULT rendered", sc.frame_start, sc.frame_end)
