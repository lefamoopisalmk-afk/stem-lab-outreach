"""Build the STEM Lab robot head, its 5:00 seamless loop, loop.blend and loop.glb.
Run: blender -b --factory-startup --python-exit-code 1 -P build_loop.py -- <out_dir>
"""
import bpy, bmesh, sys, json, math, os, random
from math import radians, cos, sin, pi
from mathutils import Quaternion, Vector, Matrix

OUT = sys.argv[sys.argv.index("--") + 1]
FPS, TOTAL_S = 24, 300
END = FPS * TOTAL_S  # 7200

# ---------------------------------------------------------------- scene reset
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
sc = bpy.context.scene
col = sc.collection


def srgb(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in c] + [1]


def mat(name, hexcol, metal=0., rough=.5, emit=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = srgb(hexcol)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = srgb(hexcol)
        b.inputs["Emission Strength"].default_value = 1.0
    return m


M = dict(
    shell=mat("Shell_Pearl", "E8EDF4", 0, .38),
    visor=mat("Visor_Navy", "10253F", .2, .25),
    dark=mat("Trim_Navy", "1B3A5C", .3, .45),
    gear=mat("Gear_Orange", "FF7A1A", .25, .4),
    eye=mat("Eye_Teal", "2FE6D0", 0, .3, True),
    led=mat("LED_Orange", "FFB347", 0, .3, True),
    logo=mat("Logo_Navy", "10253F", 0, .5),
)


def new_obj(name, bm, material_list, parent=None, loc=(0, 0, 0), sharp=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in material_list:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob.location = loc
    ob.rotation_mode = 'QUATERNION'
    if parent:
        ob.parent = parent
    me.shade_smooth()
    if sharp:
        me.set_sharp_from_angle(angle=radians(sharp))
    return ob


def rbox(bm, size, center, bevel, segs=4):
    r = bmesh.ops.create_cube(bm, size=1)
    vs = r["verts"]
    for v in vs:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2])) + Vector(center)
    edges = list({e for v in vs for e in v.link_edges})
    bmesh.ops.bevel(bm, geom=vs + edges, offset=bevel, offset_type='OFFSET', segments=segs,
                    profile=.5, affect='EDGES', clamp_overlap=True)


def add_part(bm, builder, mi):
    """run builder(bm) and set the material index on the faces it created"""
    before = set(bm.faces)
    builder(bm)
    for f in bm.faces:
        if f not in before:
            f.material_index = mi


def cyl(bm, r1, r2, depth, center, segs=24, axis='Z'):
    rot = Matrix.Identity(4)
    if axis == 'X':
        rot = Matrix.Rotation(pi / 2, 4, 'Y')
    if axis == 'Y':
        rot = Matrix.Rotation(pi / 2, 4, 'X')
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r1, radius2=r2, depth=depth,
                          matrix=Matrix.Translation(center) @ rot)


# ---------------------------------------------------------------- head (root)
bm = bmesh.new()
add_part(bm, lambda b: rbox(b, (1.6, 1.3, 1.3), (0, 0, 0), .2), 0)                       # shell
add_part(bm, lambda b: rbox(b, (1.28, .08, .68), (0, -.645, -.12), .11, 4), 1)           # visor
add_part(bm, lambda b: cyl(b, .3, .3, .22, (0, 0, -.74), 28), 2)                         # neck
add_part(bm, lambda b: rbox(b, (.92, .78, .12), (0, 0, -.88), .05, 3), 2)                # collar
add_part(bm, lambda b: cyl(b, .1, .1, .1, (0, 0, .68), 16), 2)                           # antenna socket
for s in (-1, 1):
    add_part(bm, lambda b: cyl(b, .17, .17, .1, (s * .82, 0, 0), 20, 'X'), 2)            # axle boss
for i in range(5):                                                                       # mouth LEDs
    x = (i - 2) * .115
    add_part(bm, lambda b: rbox(b, (.08, .02, .05), (x, -.692, -.31), .012, 1), 3)
head = new_obj("Robot_Head", bm, [M["shell"], M["visor"], M["dark"], M["led"]], sharp=35)
wn = head.modifiers.new("WeightedNormal", 'WEIGHTED_NORMAL')
wn.keep_sharp = True
wn.weight = 100

# ---------------------------------------------------------------- logo text
cu = bpy.data.curves.new("LogoText", 'FONT')
cu.body = "STEM LAB"
cu.align_x, cu.align_y = 'CENTER', 'CENTER'
cu.size = .235
cu.extrude = .006
cu.offset = .004
cu.resolution_u = 2
cu.space_character = 1.04
tmp = bpy.data.objects.new("LogoText", cu)
col.objects.link(tmp)
bpy.context.view_layer.update()
me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
bpy.data.objects.remove(tmp)
bpy.data.curves.remove(cu)
me.transform(Matrix.Translation((0, -.655, .42)) @ Matrix.Rotation(pi / 2, 4, 'X'))
me.materials.clear()
me.materials.append(M["logo"])
logo = bpy.data.objects.new("Logo", me)
me.name = "Logo"
col.objects.link(logo)
logo.parent = head
me.shade_flat()

# ---------------------------------------------------------------- eyes (blink + dart)
EYE_Y, EYE_Z = -.69, -.02
bm = bmesh.new()
for s in (-1, 1):
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=1,
                              matrix=Matrix.Translation((s * .3, 0, 0)) @ Matrix.Diagonal((.135, .025, .15, 1)))
eyes = new_obj("Eyes", bm, [M["eye"]], parent=head, loc=(0, EYE_Y, EYE_Z))


# ---------------------------------------------------------------- gears
def gear_bm(teeth=12, r_out=.35, r_root=.27, width=.09):
    bm = bmesh.new()
    prof = []
    for i in range(teeth):
        a = 2 * pi * i / teeth
        p = 2 * pi / teeth
        for da, r in ((-.27, r_root), (-.14, r_out), (.14, r_out), (.27, r_root)):
            t = a + da * p
            prof.append((cos(t) * r, sin(t) * r))
    # gear profile on the YZ plane; X is the axle
    fr = [bm.verts.new((-width / 2, y, z)) for y, z in prof]
    bk = [bm.verts.new((width / 2, y, z)) for y, z in prof]
    bm.faces.new(list(reversed(fr)))
    bm.faces.new(bk)
    N = len(prof)
    for i in range(N):
        j = (i + 1) % N
        bm.faces.new((fr[i], fr[j], bk[j], bk[i]))
    before = set(bm.faces)
    cyl(bm, .1, .1, width + .05, (0, 0, 0), 16, 'X')
    for f in bm.faces:
        if f not in before:
            f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return bm


gear_l = new_obj("Gear_L", gear_bm(), [M["gear"], M["dark"]], parent=head, loc=(-.92, 0, 0), sharp=30)
gear_r = new_obj("Gear_R", gear_bm(), [M["gear"], M["dark"]], parent=head, loc=(.92, 0, 0), sharp=30)

# ---------------------------------------------------------------- antenna
bm = bmesh.new()
add_part(bm, lambda b: cyl(b, .035, .025, .34, (0, 0, .17), 10), 0)
add_part(bm, lambda b: bmesh.ops.create_uvsphere(b, u_segments=16, v_segments=10, radius=.085,
                                                 matrix=Matrix.Translation((0, 0, .39))), 1)
antenna = new_obj("Antenna", bm, [M["dark"], M["led"]], parent=head, loc=(0, 0, .7))


# ---------------------------------------------------------------- choreography
def aa_q(axis, th):
    """Axis-angle without wrapping. Quaternion(axis, angle) wraps past 180 degrees, which flips
    the sign between neighbouring keys and makes a curve snap through zero."""
    c, h = cos(th / 2), sin(th / 2)
    return Quaternion((c, axis[0] * h, axis[1] * h, axis[2] * h))


def euler_q(yaw=0, pitch=0, roll=0):
    return (Quaternion((0, 0, 1), radians(yaw)) @ Quaternion((1, 0, 0), radians(pitch))
            @ Quaternion((0, 1, 0), radians(roll)))


def P(x=0, y=0, z=0, yaw=0, pitch=0, roll=0, sx=1, sy=None, sz=None):
    return dict(pos=(x, y, z), yaw=yaw, pitch=pitch, roll=roll,
                scl=(sx, sx if sy is None else sy, sx if sz is None else sz))


POSE = dict(
    home=P(),
    look_l=P(yaw=-30, roll=-4, z=.02),
    look_r=P(yaw=30, roll=4, z=.02),
    look_up=P(pitch=-16, z=.07),
    nod=P(pitch=17, z=-.05),
    tilt_l=P(roll=-13, yaw=-8),
    tilt_r=P(roll=13, yaw=8),
    crouch=P(z=-.17, sx=1.07, sy=1.07, sz=.9),
    hop=P(z=.3, sx=.95, sy=.95, sz=1.07),
    land=P(z=-.11, sx=1.09, sy=1.09, sz=.88),
    lean_in=P(y=-.5, z=-.02, pitch=6, sx=1.13),
    lean_back=P(y=.6, z=.04, pitch=-7, sx=.84),
    slide_l=P(x=-.2, yaw=-16, roll=-7),
    slide_r=P(x=.2, yaw=16, roll=7),
    big=P(z=.03, sx=1.17),
    small=P(z=-.1, sx=.78),
    curious_l=P(x=-.12, y=-.25, yaw=-22, roll=-11, pitch=5, sx=1.06),
    curious_r=P(x=.12, y=-.25, yaw=22, roll=11, pitch=5, sx=1.06),
)

# (pose, travel seconds, hold seconds) or ("SPIN", axis, direction, seconds)
SEQ = [
    # act 1: wake up and look around
    ("look_l", 2.0, 1.6), ("home", 1.4, .8), ("look_r", 2.0, 1.6), ("home", 1.4, 1.0),
    ("look_up", 1.6, 1.4), ("nod", 1.0, .3), ("look_up", .8, .3), ("nod", .8, .3), ("home", 1.2, 1.2),
    ("tilt_l", 1.4, 1.2), ("tilt_r", 1.6, 1.2), ("home", 1.2, 1.4),
    ("slide_l", 2.2, 1.4), ("slide_r", 2.8, 1.4), ("home", 1.8, 1.6),
    # act 2: hops and leans
    ("crouch", 1.0, .3), ("hop", .55, .05), ("land", .5, .2), ("home", .9, 1.2),
    ("crouch", 1.0, .3), ("hop", .55, .05), ("land", .5, .2), ("hop", .55, .05), ("land", .5, .2), ("home", 1.0, 1.4),
    ("lean_back", 2.0, .8), ("lean_in", 2.2, 1.8), ("nod", 1.2, .4), ("lean_in", 1.0, 1.0), ("home", 1.8, 1.2),
    ("curious_l", 1.8, 1.8), ("curious_r", 2.2, 1.8), ("home", 1.6, 1.4),
    # act 3: spin turns
    ("crouch", 1.0, .3), ("SPIN", "Z", 1, 3.6), ("land", .6, .2), ("home", 1.0, 2.0),
    ("look_l", 1.4, 1.0), ("look_r", 1.6, 1.0), ("home", 1.2, 1.2),
    ("crouch", 1.0, .3), ("SPIN", "Z", -1, 3.6), ("land", .6, .2), ("home", 1.0, 2.0),
    ("tilt_r", 1.2, 1.0), ("nod", 1.0, .5), ("home", 1.1, 1.4),
    ("small", 2.4, 1.6), ("big", 2.6, 1.8), ("home", 1.8, 1.4),
    # act 4: size play and curiosity
    ("lean_back", 2.2, 1.2), ("look_up", 1.4, 1.0), ("lean_in", 2.2, 1.6), ("tilt_l", 1.2, 1.0), ("home", 1.4, 1.4),
    ("small", 1.8, .8), ("hop", .9, .1), ("land", .6, .2), ("big", 1.2, 1.4), ("home", 1.4, 1.2),
    ("slide_r", 1.8, 1.0), ("curious_r", 1.2, 1.4), ("slide_l", 2.6, 1.0), ("curious_l", 1.2, 1.4), ("home", 1.6, 1.8),
    # act 5: flip, bow and settle back to the first pose
    ("crouch", 1.2, .4), ("SPIN", "X", 1, 3.2), ("land", .6, .3), ("home", 1.0, 2.2),
    ("nod", 1.4, 1.2), ("home", 1.2, 1.0), ("look_l", 1.4, .8), ("look_r", 1.6, .8), ("home", 1.2, 1.4),
    ("crouch", 1.2, .4), ("SPIN", "X", -1, 3.2), ("land", .6, .3), ("home", 1.0, 2.0),
    ("look_up", 1.6, 1.2), ("nod", 1.4, 1.4), ("home", 1.8, 0),
]

# Five minutes is long, so acts 1 and 2 come back mirrored left to right before the finale:
# the fifth act is reached without the viewer ever seeing the same minute twice.
MIRROR = {"look_l": "look_r", "look_r": "look_l", "tilt_l": "tilt_r", "tilt_r": "tilt_l", "slide_l": "slide_r",
          "slide_r": "slide_l", "curious_l": "curious_r", "curious_r": "curious_l"}
ACT3 = next(i for i, s in enumerate(SEQ) if s[0] == "SPIN") - 1   # the crouch before the first spin
ACT5 = [i for i, s in enumerate(SEQ) if s[0] == "SPIN"][2] - 1    # the crouch before the first flip
full = SEQ[:ACT5] + [(MIRROR.get(s[0], s[0]), s[1], s[2]) for s in SEQ[:ACT3]] + SEQ[ACT5:]
t_sum = sum(s[3] if s[0] == "SPIN" else s[1] for s in full)
h_sum = sum(0 if s[0] == "SPIN" else s[2] for s in full)
hold_k = (TOTAL_S - t_sum) / h_sum   # stretch the holds so the loop is exactly 5:00
print("travel", t_sum, "hold", h_sum, "hold_k", hold_k)
assert hold_k > .2, hold_k

# keys: (frame, value); rotation keys also carry a tangent per frame, the rest are flat
pos_k, scl_k, rot_k = [], [], []
moves = []  # used by the antenna and the eyes
cur_q = Quaternion((1, 0, 0, 0))
cur_name = "home"
t = 0.0
bob = 1


def push(f, pose, q, offs=(0, 0, 0)):
    pos_k.append((f, tuple(a + b for a, b in zip(pose["pos"], offs))))
    scl_k.append((f, pose["scl"]))
    rot_k.append((f, tuple(q), (0, 0, 0, 0)))


push(0, POSE["home"], cur_q)
for s in full:
    f0 = round(t * FPS)
    if s[0] == "SPIN":
        _, axis, sign, T = s
        f1 = round((t + T) * FPS)
        ax = Vector({"Z": (0, 0, 1), "X": (1, 0, 0)}[axis])
        n = 8
        for i in range(1, n + 1):
            u = i / n
            th = sign * 2 * pi * (3 * u * u - 2 * u * u * u)
            dth = sign * 2 * pi * (6 * u - 6 * u * u) / (f1 - f0)  # radians per frame
            qa = aa_q(ax, th)
            q = cur_q @ qa
            dq = cur_q @ qa @ Quaternion((0, ax.x, ax.y, ax.z))    # dq/dt = 1/2 q (0, w)
            rot_k.append((f0 + round((f1 - f0) * u), tuple(q), tuple(.5 * dth * c for c in dq)))
        cur_q = q.copy()
        mid = (f0 + f1) // 2                                       # arc in the air
        pos_k.append((mid, (0, 0, .34)))
        scl_k.append((mid, (.96, .96, 1.05)))
        pos_k.append((f1, POSE["crouch"]["pos"]))
        scl_k.append((f1, POSE["crouch"]["scl"]))
        moves.append(dict(f0=f0, f1=f1, a=cur_name, b="crouch", spin=True))
        cur_name = "crouch"
        t += T
        continue
    name, travel, hold = s
    hold *= hold_k
    pose = POSE[name]
    f1 = round((t + travel) * FPS)
    tgt = euler_q(pose["yaw"], pose["pitch"], pose["roll"])
    if tgt.dot(cur_q) < 0:
        tgt = Quaternion(tuple(-c for c in tgt))
    push(f1, pose, tgt)
    moves.append(dict(f0=f0, f1=f1, a=cur_name, b=name, spin=False))
    cur_q, cur_name = tgt, name
    t += travel
    if hold > .01:
        f2 = round((t + hold) * FPS)
        bob = -bob
        if f1 + 1 < f2 < END:
            push(f2, pose, tgt, (0, 0, .012 * bob))     # small drift so a hold is never dead
        t += hold

assert abs(t - TOTAL_S) < 1e-6, t
assert pos_k[-1][0] == END and rot_k[-1][0] == END, (pos_k[-1], rot_k[-1])
assert cur_name == "home"
print("final root q", tuple(cur_q))

# ---- gears: 8 whole turns in 96 eased 30 degree pulses (720k degrees returns q to +1)
GEAR_STEPS = 96
gear_frames = [round(END * i / GEAR_STEPS) for i in range(GEAR_STEPS + 1)]
gear_l_k = [(f, tuple(aa_q((1, 0, 0), radians(30 * i))), (0, 0, 0, 0)) for i, f in enumerate(gear_frames)]
gear_r_k = [(f, tuple(aa_q((1, 0, 0), -radians(30 * i))), (0, 0, 0, 0)) for i, f in enumerate(gear_frames)]


def clean(keys):
    """sort, keep one key per frame, minimum gap of 2 frames"""
    out = []
    for k in sorted(keys, key=lambda k: k[0]):
        if not out or k[0] - out[-1][0] >= 2:
            out.append(k)
    return out


# ---- antenna: drags behind every head move, overshoots, then settles (overlap)
ant = [(0, (0, 0))]
for m in moves:
    a, b = POSE[m["a"]], POSE[m["b"]]
    if m["spin"]:
        kick = (0., 16.)
    else:
        dx = b["pos"][0] - a["pos"][0] + (b["roll"] - a["roll"]) * .012 + (b["yaw"] - a["yaw"]) * .004
        dy = b["pos"][1] - a["pos"][1] + (b["pitch"] - a["pitch"]) * .012
        kick = (-dx * 42, dy * 30)
    if abs(kick[0]) + abs(kick[1]) < 1:
        continue
    k = (max(-20, min(20, kick[0])), max(-20, min(20, kick[1])))
    T = m["f1"] - m["f0"]
    ant.append((m["f0"] + 1, (0, 0)))
    ant.append((m["f0"] + round(T * .45), k))
    ant.append((m["f1"] + 5, (-k[0] * .55, -k[1] * .55)))
    ant.append((m["f1"] + 14, (k[0] * .2, k[1] * .2)))
    ant.append((m["f1"] + 24, (0, 0)))
ant = [k for k in clean(ant) if k[0] < END - 2] + [(END, (0, 0))]
ant_k = [(f, tuple(Quaternion((0, 1, 0), radians(ty)) @ Quaternion((1, 0, 0), radians(tx))), (0, 0, 0, 0))
         for f, (ty, tx) in ant]

# ---- eyes: dart ahead of the head, blink on an irregular beat
eye_rest = Vector((0, EYE_Y, EYE_Z))
eye_loc = [(0, tuple(eye_rest))]
cx = 0.
for m in moves:
    nx = max(-.06, min(.06, POSE[m["b"]]["yaw"] * .0025))
    if abs(nx - cx) < .005:
        continue
    f = m["f0"]
    if f - 6 > eye_loc[-1][0] + 2:
        eye_loc.append((f - 6, tuple(eye_rest + Vector((cx, 0, 0)))))
        eye_loc.append((f, tuple(eye_rest + Vector((nx, 0, 0)))))
        cx = nx
eye_loc.append((END, tuple(eye_rest)))
eye_scl = [(0, (1, 1, 1))]
rng = random.Random(21)
f = 60
while f < END - 60:
    for _ in range(2 if rng.random() < .18 else 1):
        eye_scl += [(f, (1, 1, 1)), (f + 3, (1, 1, .1)), (f + 7, (1, 1, 1))]
        f += 12
    f += rng.randint(70, 190)
eye_scl.append((END, (1, 1, 1)))
eye_scl = clean(eye_scl)
assert eye_scl[-1][0] == END

# ---------------------------------------------------------------- write f-curves
action = bpy.data.actions.new("RobotLoop")
layer = action.layers.new("Base")
strip = layer.strips.new(type='KEYFRAME')


def bezier_curve(cb, path, idx, keys):
    """keys: (frame, value, slope per frame). Handles sit at 1/3 of each segment, so the
    Blender curve and the glTF Hermite spline are the same curve (time stays linear)."""
    fc = cb.fcurves.new(path, index=idx)
    n = len(keys)
    fc.keyframe_points.add(n)
    for i, (f, v, s) in enumerate(keys):
        kp = fc.keyframe_points[i]
        kp.co = (f, v)
        kp.interpolation = 'BEZIER'
        kp.handle_left_type = kp.handle_right_type = 'FREE'
        dl = (f - keys[i - 1][0]) / 3 if i else 8
        dr = (keys[i + 1][0] - f) / 3 if i < n - 1 else 8
        kp.handle_left = (f - dl, v - s * dl)
        kp.handle_right = (f + dr, v + s * dr)
    fc.update()


def animate(ob, loc=None, rot=None, scl=None):
    slot = action.slots.new(id_type='OBJECT', name=ob.name)
    cb = strip.channelbag(slot, ensure=True)
    if loc:
        for i in range(3):
            bezier_curve(cb, "location", i, [(f, v[i], 0) for f, v in loc])
    if rot:
        for i in range(4):
            bezier_curve(cb, "rotation_quaternion", i, [(k[0], k[1][i], k[2][i]) for k in rot])
    if scl:
        for i in range(3):
            bezier_curve(cb, "scale", i, [(f, v[i], 0) for f, v in scl])
    ad = ob.animation_data_create()
    ad.action = action
    ad.action_slot = slot


animate(head, loc=pos_k, rot=rot_k, scl=scl_k)
animate(gear_l, rot=gear_l_k)
animate(gear_r, rot=gear_r_k)
animate(antenna, rot=ant_k)
animate(eyes, loc=eye_loc, scl=eye_scl)
action.use_frame_range = True
action.frame_start, action.frame_end = 0, END
action.use_cyclic = True

# ---------------------------------------------------------------- camera, lights, scene settings
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 0, END - 1   # frame 7200 == frame 0, so playback never shows it twice
sc.frame_set(0)
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
cam = bpy.data.cameras.new("Cam")
cam.lens = 50
co = bpy.data.objects.new("Camera", cam)
col.objects.link(co)
co.location = (1.75, -8.6, 1.3)                    # slightly right and above, so a gear face and the top read
aim = Vector((0, 0, .18)) - Vector(co.location)
co.rotation_mode = 'QUATERNION'
co.rotation_quaternion = aim.to_track_quat('-Z', 'Y')
sc.camera = co
for name, en, loc, rot in (
        ("Key", 3.2, (3, -4, 5), (radians(52), 0, radians(32))),
        ("Fill", 1.0, (-4, -3, 1), (radians(80), 0, radians(-52))),
        ("Rim", 2.0, (0, 5, 4), (radians(-48), 0, 0))):
    l = bpy.data.lights.new(name, 'SUN')
    l.energy = en
    lo = bpy.data.objects.new(name, l)
    col.objects.link(lo)
    lo.location, lo.rotation_euler = loc, rot
w = bpy.data.worlds.new("World")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = srgb("0E2A47")
w.node_tree.nodes["Background"].inputs[1].default_value = .7
sc.world = w
sc.view_settings.view_transform = 'Standard'
bpy.context.view_layer.update()

# ---------------------------------------------------------------- save + export
os.makedirs(os.path.join(OUT, "source"), exist_ok=True)
bpy.context.preferences.filepaths.save_version = 0   # no loop.blend1 backup next to the deliverable
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "loop.blend"), compress=True)
bpy.ops.export_scene.gltf(
    filepath=os.path.join(OUT, "loop.glb"), export_format='GLB', use_selection=False,
    export_animations=True, export_animation_mode='ACTIONS', export_force_sampling=False,
    export_frame_range=False, export_apply=True, export_yup=True,
    export_cameras=False, export_lights=False, export_texcoords=False, export_normals=True,
    export_tangents=False, export_draco_mesh_compression_enable=False)


def write_exact_rotation_keys(path, sources):
    """The glTF exporter rewrites each rotation key with w >= 0 and damages some tangents (a key
    where w is near zero came out with a tangent of -48). The rotation is the same, but CUBICSPLINE
    interpolates component by component, so a flipped key snaps through zero and a gear whips
    backwards. Write the authored keys and tangents into the BIN chunk instead."""
    import struct
    data = bytearray(open(path, "rb").read())
    jlen = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + jlen])
    bin0 = 20 + jlen + 8
    to_gltf = lambda q: [q[1], q[3], -q[2], q[0]]     # Blender (w, x, y, z) to glTF (x, y, z, w), Y up
    done = 0
    for anim in gltf["animations"]:
        for ch in anim["channels"]:
            if ch["target"]["path"] != "rotation":
                continue
            keys = sources[gltf["nodes"][ch["target"]["node"]]["name"]]
            sampler = anim["samplers"][ch["sampler"]]
            assert sampler["interpolation"] == "CUBICSPLINE"
            acc_t, acc = gltf["accessors"][sampler["input"]], gltf["accessors"][sampler["output"]]
            assert acc_t["count"] == len(keys) and acc["count"] == len(keys) * 3, (acc_t["count"], len(keys))
            bv = gltf["bufferViews"][acc["bufferView"]]
            off = bin0 + bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
            vals = []
            for f, q, dq in keys:
                tan = [c * FPS for c in to_gltf(dq)]
                vals += tan + to_gltf(q) + tan
            struct.pack_into("<%df" % len(vals), data, off, *vals)
            acc["min"] = [min(vals[i::4]) for i in range(4)]
            acc["max"] = [max(vals[i::4]) for i in range(4)]
            done += 1
    new_json = json.dumps(gltf, separators=(",", ":")).encode()
    new_json += b" " * (-len(new_json) % 4)
    out = data[:12] + struct.pack("<II", len(new_json), 0x4E4F534A) + new_json + data[bin0 - 8:]
    struct.pack_into("<I", out, 8, len(out))
    open(path, "wb").write(out)
    return done


print("rotation channels rewritten", write_exact_rotation_keys(os.path.join(OUT, "loop.glb"), {
    "Robot_Head": rot_k, "Gear_L": gear_l_k, "Gear_R": gear_r_k, "Antenna": ant_k}))

# reference samples used to prove the GLB matches Blender
ref = dict(fps=FPS)
animated = (head, gear_l, gear_r, antenna, eyes)
for ob in animated:
    ref[ob.name] = []
for f in range(0, END + 1, 13):
    sc.frame_set(f)
    bpy.context.view_layer.update()
    for ob in animated:
        ref[ob.name].append(dict(f=f, loc=tuple(ob.location), rot=tuple(ob.rotation_quaternion.normalized()),
                                 scl=tuple(ob.scale)))
sc.frame_set(0)
with open(os.path.join(OUT, "source", "blender_samples.json"), "w") as fh:
    json.dump(ref, fh)
print("RESULT", json.dumps(dict(hold_k=round(hold_k, 3), root_keys=len(pos_k), rot_keys=len(rot_k),
                                ant=len(ant_k), blink=len(eye_scl), eye_loc=len(eye_loc),
                                glb=os.path.getsize(os.path.join(OUT, "loop.glb")),
                                blend=os.path.getsize(os.path.join(OUT, "loop.blend")))))
