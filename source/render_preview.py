"""Render the 5-second preview: the last 2.5 s of the loop followed by the first 2.5 s, so the
join between the end and the start plays in the middle of the clip (at 0:02.5).
Run: blender -b loop.blend --python-exit-code 1 -P render_preview.py -- <png_folder>
Then: ffmpeg -framerate 24 -i <png_folder>/f%04d.png -c:v libx264 -crf 20 -pix_fmt yuv420p -movflags +faststart preview.mp4
"""
import bpy, os, sys

out = sys.argv[sys.argv.index("--") + 1]
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
end = sc.frame_end + 1                     # 7200, the same pose as frame 0
frames = list(range(end - 60, end)) + list(range(0, 60))
for i, f in enumerate(frames):
    sc.frame_set(f)
    sc.render.filepath = os.path.join(out, "f%04d.png" % i)
    bpy.ops.render.render(write_still=True)
print("RESULT rendered", len(frames), "frames, first", frames[0], "last", frames[-1])
