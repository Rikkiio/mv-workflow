"""GPU 2.5D compositor (moderngl).

World space: x right, y down, z away from camera; the plane z=0 maps 1:1 to pixels when the camera
sits at z=-FOCAL, and the world origin is at the screen centre. Screen space: pixels, origin top-left.
All textures are premultiplied RGBA.
"""
import math
import os

import cv2
import moderngl
import numpy as np

W, H, FPS = 1920, 1080, 30
FOCAL = 1400.0

_SPRITE_VS = """
#version 430
in vec2 v_corner; in vec2 v_uvbase;
in vec3 i_pos; in vec2 i_size; in vec3 i_rot; in vec4 i_uv; in vec4 i_col; in vec3 i_add;
uniform vec3 u_cam; uniform float u_roll; uniform float u_f; uniform int u_screen; uniform vec2 u_res;
uniform vec4 u_warp; uniform vec4 u_warp2; uniform float u_time; uniform vec2 u_shift;
out vec2 f_uv; out vec4 f_col; out vec3 f_add; out vec2 f_luv;
mat3 rx(float a){float c=cos(a),s=sin(a);return mat3(1,0,0, 0,c,s, 0,-s,c);}
mat3 ry(float a){float c=cos(a),s=sin(a);return mat3(c,0,-s, 0,1,0, s,0,c);}
mat3 rz(float a){float c=cos(a),s=sin(a);return mat3(c,s,0, -s,c,0, 0,0,1);}
void main(){
  vec2 c = v_corner;
  if (u_warp.x != 0.0) {           // hanging-cloth sway, growing below anchor u_warp.w
    float w = smoothstep(u_warp.w, 1.0, v_uvbase.y);
    c.x += u_warp.x * w * sin(v_uvbase.y * u_warp.y * 6.2831853 - u_time * u_warp.z) / i_size.x;
  }
  if (u_warp2.x != 0.0) {          // breathing / bob: vertical squash around the bottom edge
    float s = 1.0 + u_warp2.x * sin(u_time * u_warp2.y + u_warp2.z);
    c.y = 0.5 - (0.5 - c.y) * s;
  }
  vec3 P = i_pos + rz(i_rot.z) * ry(i_rot.y) * rx(i_rot.x) * vec3(c * i_size, 0.0);
  if (u_screen == 1) {
    gl_Position = vec4(P.x / u_res.x * 2.0 - 1.0, 1.0 - P.y / u_res.y * 2.0, 0.0, 1.0);
  } else {
    vec3 v = P - u_cam;
    float cr = cos(u_roll), sr = sin(u_roll);
    v.xy = vec2(cr * v.x + sr * v.y, -sr * v.x + cr * v.y);
    float z = max(v.z, 1.0);
    vec2 sh = u_shift / (u_res * 0.5) * z;      // lens shift in pixels (a tilt without keystone)
    gl_Position = vec4(u_f * v.x / (u_res.x * 0.5) + sh.x, -u_f * v.y / (u_res.y * 0.5) - sh.y, 0.0, z);
  }
  f_uv = mix(i_uv.xy, i_uv.zw, v_uvbase);
  f_luv = v_uvbase; f_col = i_col; f_add = i_add;
}
"""

_SPRITE_FS = """
#version 430
in vec2 f_uv; in vec4 f_col; in vec3 f_add; in vec2 f_luv;
uniform sampler2D u_tex; uniform int u_mode; uniform vec4 u_rim; uniform vec2 u_rimoff;
uniform sampler2D u_mask; uniform int u_usemask; uniform vec2 u_res; uniform vec4 u_cut;
out vec4 frag;
void main(){
  vec4 t = texture(u_tex, f_uv);
  vec4 m = vec4(f_col.rgb * f_col.a, f_col.a);
  vec4 c;
  if (u_mode == 1) {                 // solid silhouette
    c = vec4(f_col.rgb, 1.0) * t.a * f_col.a;
  } else if (u_mode == 2) {          // silhouette + rim light
    float a2 = texture(u_tex, f_uv + u_rimoff).a;
    float rim = clamp(t.a - a2, 0.0, 1.0);
    c = vec4(mix(f_col.rgb, u_rim.rgb, rim * u_rim.a), 1.0) * t.a * f_col.a;
  } else if (u_mode == 3) {          // alpha-only texture used as coverage for a flat colour
    c = m * t.r;
  } else {
    c = t * m;
    c.rgb += f_add * c.a;
  }
  if (u_cut.z > 0.0) {               // soft linear reveal in local uv: cut.xy dir, z progress, w softness
    float s = dot(f_luv - 0.5, u_cut.xy) + 0.5;
    c *= 1.0 - smoothstep(u_cut.z - u_cut.w, u_cut.z, s);
  }
  if (u_usemask != 0) {
    float mk = texture(u_mask, gl_FragCoord.xy / u_res).a;
    c *= (u_usemask == 1) ? mk : (1.0 - mk);
  }
  frag = c;
}
"""

_FS_QUAD_VS = """
#version 430
in vec2 v_pos;
void main(){ gl_Position = vec4(v_pos, 0.0, 1.0); }
"""

_NOISE = """
float hash(vec2 p){ p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float vnoise(vec2 p){ vec2 i = floor(p), f = fract(p); vec2 u = f*f*(3.0-2.0*f);
  return mix(mix(hash(i), hash(i+vec2(1,0)), u.x), mix(hash(i+vec2(0,1)), hash(i+vec2(1,1)), u.x), u.y); }
float fbm(vec2 p){ float s = 0.0, a = 0.5; for (int i = 0; i < 5; i++){ s += a * vnoise(p); p *= 2.03; a *= 0.5; } return s; }
"""

# SDF shapes drawn in screen space (pixel coordinates, y down)
_SHAPE_FS = """
#version 430
uniform vec2 u_res; uniform int u_type; uniform vec2 u_c; uniform vec4 u_p; uniform vec4 u_col;
uniform float u_soft; uniform vec2 u_arc; uniform float u_rough; uniform float u_seed; uniform float u_rot;
out vec4 frag;
""" + _NOISE + """
void main(){
  vec2 px = vec2(gl_FragCoord.x, u_res.y - gl_FragCoord.y);
  vec2 p = px - u_c;
  float cr = cos(u_rot), sr = sin(u_rot); p = vec2(cr*p.x + sr*p.y, -sr*p.x + cr*p.y);
  float d;
  float ang = atan(p.y, p.x);                      // -pi..pi, 0 = +x, clockwise on screen
  if (u_type == 0) {                               // disc radius p.x
    d = length(p) - u_p.x;
  } else if (u_type == 1) {                        // ring radius p.x thickness p.y, arc u_arc (radians)
    float a = mod(ang - u_arc.x, 6.2831853);
    float span = u_arc.y - u_arc.x;
    float r = length(p);
    float th = u_p.y;
    if (u_p.z > 0.0) {                             // brush taper along the arc
      float k = clamp(a / max(span, 1e-4), 0.0, 1.0);
      th *= mix(0.35, 1.0, smoothstep(0.0, 0.18, k)) * mix(1.0, 0.55, smoothstep(0.7, 1.0, k));
    }
    d = abs(r - u_p.x) - th * 0.5;
    if (span < 6.283) {
      if (a > span) {
        vec2 e0 = u_p.x * vec2(cos(u_arc.x), sin(u_arc.x));
        vec2 e1 = u_p.x * vec2(cos(u_arc.y), sin(u_arc.y));
        d = min(length(p - e0), length(p - e1)) - th * 0.5 * (u_p.z > 0.0 ? 0.5 : 1.0);
      }
    }
  } else if (u_type == 2) {                        // rounded rect half-size p.xy radius p.z
    vec2 q = abs(p) - u_p.xy + u_p.z; d = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - u_p.z;
  } else {                                         // segment from c to c+p.xy, width p.z
    vec2 b = u_p.xy; float h = clamp(dot(p, b) / dot(b, b), 0.0, 1.0); d = length(p - b * h) - u_p.z * 0.5;
  }
  if (u_rough > 0.0) d += (fbm(px * 0.035 + u_seed) - 0.5) * u_rough;
  float a = 1.0 - smoothstep(-0.75, 0.75 + u_soft, d);
  frag = vec4(u_col.rgb * u_col.a, u_col.a) * a;
}
"""

_RAYS_FS = """
#version 430
uniform vec2 u_res; uniform vec2 u_c; uniform float u_n; uniform float u_rot; uniform float u_width;
uniform vec2 u_rad; uniform vec4 u_col; uniform float u_soft;
out vec4 frag;
void main(){
  vec2 px = vec2(gl_FragCoord.x, u_res.y - gl_FragCoord.y);
  vec2 p = px - u_c; float r = length(p);
  float a = atan(p.y, p.x) + u_rot;
  float f = fract(a / 6.2831853 * u_n);
  float tri = abs(f - 0.5) * 2.0;                  // 0 at ray centre .. 1 between rays
  float ray = 1.0 - smoothstep(u_width - u_soft, u_width + u_soft, tri);
  float rad = smoothstep(u_rad.x * 0.6, u_rad.x, r) * (1.0 - smoothstep(u_rad.x, u_rad.y, r));
  float al = ray * rad * u_col.a;
  frag = vec4(u_col.rgb * al, al);
}
"""

_GRAD_FS = """
#version 430
uniform vec2 u_res; uniform int u_type; uniform vec2 u_a; uniform vec2 u_b;
uniform vec4 u_c0; uniform vec4 u_c1; uniform vec4 u_c2; uniform vec3 u_pos;
out vec4 frag;
void main(){
  vec2 px = vec2(gl_FragCoord.x, u_res.y - gl_FragCoord.y);
  float t;
  if (u_type == 0) { vec2 d = u_b - u_a; t = dot(px - u_a, d) / dot(d, d); }
  else { t = length(px - u_a) / max(length(u_b - u_a), 1.0); }
  t = clamp(t, 0.0, 1.0);
  vec4 c = t < u_pos.y ? mix(u_c0, u_c1, smoothstep(u_pos.x, u_pos.y, t)) : mix(u_c1, u_c2, smoothstep(u_pos.y, u_pos.z, t));
  frag = vec4(c.rgb * c.a, c.a);
}
"""

_BRIGHT_FS = """
#version 430
uniform sampler2D u_src; uniform vec2 u_res; uniform float u_thr;
out vec4 frag;
void main(){
  vec2 uv = gl_FragCoord.xy / u_res;
  vec3 c = texture(u_src, uv).rgb;
  float l = max(c.r, max(c.g, c.b));
  frag = vec4(c * smoothstep(u_thr, u_thr + 0.25, l), 1.0);
}
"""

_ACC_FS = """
#version 430
uniform sampler2D u_src; uniform vec2 u_res; uniform float u_w;
out vec4 frag;
void main(){ frag = texture(u_src, gl_FragCoord.xy / u_res) * u_w; }
"""

_BLUR_FS = """
#version 430
uniform sampler2D u_src; uniform vec2 u_res; uniform vec2 u_dir;
out vec4 frag;
void main(){
  vec2 uv = gl_FragCoord.xy / u_res;
  float w[5] = float[](0.2270270270, 0.1945945946, 0.1216216216, 0.0540540541, 0.0162162162);
  vec4 s = texture(u_src, uv) * w[0];
  for (int i = 1; i < 5; i++) {
    vec2 o = u_dir * float(i) * 1.6 / u_res;
    s += (texture(u_src, uv + o) + texture(u_src, uv - o)) * w[i];
  }
  frag = s;
}
"""

_TRANS_FS = """
#version 430
uniform sampler2D u_a; uniform sampler2D u_b; uniform vec2 u_res; uniform int u_mode; uniform float u_p;
uniform vec4 u_q; uniform vec4 u_col;
out vec4 frag;
""" + _NOISE + """
void main(){
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 px = vec2(gl_FragCoord.x, u_res.y - gl_FragCoord.y);
  float p = u_p;
  vec4 A = texture(u_a, uv), B = texture(u_b, uv);
  float m;                                          // 1 -> show B
  if (u_mode == 0) { m = p; }
  else if (u_mode == 1) {                           // directional wipe: q.xy dir, q.z softness(px)
    vec2 d = normalize(u_q.xy); float proj = dot(px - u_res * 0.5, d);
    float ext = 0.5 * (abs(d.x) * u_res.x + abs(d.y) * u_res.y) + u_q.z;
    m = smoothstep(-u_q.z, u_q.z, mix(-ext, ext, p) - proj);
  } else if (u_mode == 2) {                         // iris open at q.xy
    float rmax = length(max(abs(u_q.xy - vec2(0.0)), abs(u_res - u_q.xy))) * 1.05;
    m = 1.0 - smoothstep(-2.0, u_q.z + 2.0, length(px - u_q.xy) - p * rmax);
  } else if (u_mode == 3) {                         // ink bleed dissolve
    float n = fbm(px * 0.006 + u_q.w) * 0.75 + fbm(px * 0.03) * 0.25;
    m = smoothstep(n - 0.04, n + 0.04, p * 1.25 - 0.1);
  } else if (u_mode == 4) {                         // push: A slides out, B slides in along q.xy
    vec2 d = normalize(u_q.xy) * vec2(1.0, -1.0);
    float e = p < 0.5 ? 4.0*p*p*p : 1.0 - pow(-2.0*p + 2.0, 3.0) / 2.0;
    vec2 ua = uv - d * e; vec2 ub = uv - d * (e - 1.0);
    bool inB = dot(ub - 0.5, d) <= 0.5 && all(greaterThanEqual(ub, vec2(0.0))) && all(lessThanEqual(ub, vec2(1.0)));
    frag = inB ? texture(u_b, ub) : texture(u_a, ua); return;
  } else if (u_mode == 5) {                         // shoji: A splits to both sides revealing B
    float e = p < 0.5 ? 4.0*p*p*p : 1.0 - pow(-2.0*p + 2.0, 3.0) / 2.0;
    float half_ = 0.5 * e;
    if (uv.x < 0.5 - half_) { frag = texture(u_a, uv + vec2(half_, 0.0)); return; }
    if (uv.x > 0.5 + half_) { frag = texture(u_a, uv - vec2(half_, 0.0)); return; }
    frag = B; return;
  } else if (u_mode == 6) {                         // flash through colour u_col
    float k = 1.0 - abs(p * 2.0 - 1.0);
    vec4 base = p < 0.5 ? A : B;
    frag = mix(base, vec4(u_col.rgb, 1.0), smoothstep(0.0, 1.0, k) * u_col.a); return;
  } else if (u_mode == 8) {                         // strips: A cut into q.x vertical strips sliding alternately
    float n = max(u_q.x, 2.0);                      // up and down (staggered), revealing B
    float k = floor(uv.x * n);
    float dir = mod(k, 2.0) < 0.5 ? 1.0 : -1.0;
    float st = k / n * 0.35;
    float pp = clamp((p - st) / 0.65, 0.0, 1.0);
    float ee = pp * pp * (3.0 - 2.0 * pp);
    vec2 auv = uv + vec2(0.0, dir * ee * 1.05);
    if (auv.y >= 0.0 && auv.y <= 1.0) { frag = texture(u_a, auv); return; }
    frag = B; return;
  } else {                                          // zoom-through: A scales up and fades, B emerges
    float s = 1.0 + p * p * u_q.z;
    vec4 Az = texture(u_a, (uv - 0.5) / s + 0.5);
    float sb = mix(0.85, 1.0, p);
    vec4 Bz = texture(u_b, (uv - 0.5) / sb + 0.5);
    frag = mix(Az, Bz, smoothstep(0.35, 0.85, p)); return;
  }
  frag = mix(A, B, m);
}
"""

_POST_FS = """
#version 430
uniform sampler2D u_scene; uniform sampler2D u_bloom; uniform sampler2D u_paper; uniform vec2 u_res;
uniform float u_time; uniform float u_bloom_amt; uniform vec3 u_lift; uniform vec3 u_gamma; uniform vec3 u_gain;
uniform float u_sat; uniform float u_exposure; uniform float u_grain; uniform float u_vig; uniform float u_paper_amt;
uniform vec4 u_flash; uniform float u_ca; uniform vec2 u_paper_off; uniform float u_fade;
uniform float u_zb; uniform vec2 u_zbc;
uniform float u_xs; uniform float u_xr; uniform vec2 u_xo; uniform vec2 u_mb; uniform vec3 u_rb;
out vec4 frag;
""" + _NOISE + """
vec2 xf(vec2 p) {              // whole-frame camera move: zoom about the centre, roll, shift (all layers together)
  vec2 d = (p - 0.5) * u_res;
  float cr = cos(u_xr), sr = sin(u_xr);
  d = vec2(cr * d.x + sr * d.y, -sr * d.x + cr * d.y) / u_xs;
  return 0.5 + d / u_res + u_xo;
}
void main(){
  vec2 uv0 = gl_FragCoord.xy / u_res;
  vec2 uv = xf(uv0);
  vec3 c;
  if (u_rb.x != 0.0) {         // rotational blur (spins): samples turned about u_rb.yz (uv) through u_rb.x radians
    vec2 cp = u_rb.yz * u_res;
    vec2 d0 = uv * u_res - cp;
    vec3 acc = vec3(0.0);
    for (int i = 0; i < 28; i++) {
      float a = u_rb.x * (float(i) / 27.0 - 0.5);
      float ca = cos(a), sa = sin(a);
      acc += texture(u_scene, (cp + vec2(ca * d0.x - sa * d0.y, sa * d0.x + ca * d0.y)) / u_res).rgb;
    }
    c = acc / 28.0;
  } else if (u_zb > 0.0) {     // radial zoom blur: samples pulled toward the centre, stronger at the edges
    vec2 dir = uv - u_zbc;
    vec3 acc = vec3(0.0);
    for (int i = 0; i < 20; i++) {
      float s = 1.0 - u_zb * 0.16 * float(i) / 19.0;
      acc += texture(u_scene, u_zbc + dir * s).rgb;
    }
    c = acc / 20.0;
  } else if (dot(u_mb, u_mb) > 0.0) {   // directional motion blur (whip pans): samples along u_mb, in uv
    vec3 acc = vec3(0.0);
    for (int i = 0; i < 24; i++) acc += texture(u_scene, uv + u_mb * (float(i) / 23.0 - 0.5)).rgb;
    c = acc / 24.0;
  } else if (u_ca > 0.0) {
    vec2 d = (uv - 0.5) * u_ca / u_res;
    c = vec3(texture(u_scene, uv + d).r, texture(u_scene, uv).g, texture(u_scene, uv - d).b);
  } else c = texture(u_scene, uv).rgb;
  c += texture(u_bloom, uv).rgb * u_bloom_amt;
  c *= u_exposure;
  c = c * u_gain + u_lift * (1.0 - c);
  c = pow(max(c, 0.0), 1.0 / u_gamma);
  float l = dot(c, vec3(0.299, 0.587, 0.114));
  c = mix(vec3(l), c, u_sat);
  vec4 pp = texture(u_paper, uv0 + u_paper_off);
  c = mix(c, c * pp.rgb, u_paper_amt);
  c += pp.a * u_paper_amt * 0.09 * (1.0 - l) * vec3(0.95, 0.9, 0.82);
  c = mix(c, u_flash.rgb, u_flash.a);
  vec2 q = uv0 - 0.5; c *= 1.0 - u_vig * dot(q, q) * 2.2;
  float g = hash(gl_FragCoord.xy + fract(u_time * 13.17) * 917.0) - 0.5;
  c += g * u_grain * (0.6 + 0.4 * (1.0 - l));
  c *= u_fade;
  frag = vec4(clamp(c, 0.0, 1.0), 1.0);
}
"""


_GLOBE_FS = """
#version 430
uniform vec2 u_res; uniform vec2 u_c; uniform float u_r; uniform float u_rot; uniform float u_tilt;
uniform sampler2D u_map; uniform float u_glow; uniform vec4 u_rib; uniform float u_ribs; uniform float u_alpha;
uniform float u_bright; uniform float u_roll;
out vec4 frag;
void main(){
  vec2 px = vec2(gl_FragCoord.x, u_res.y - gl_FragCoord.y);
  vec2 q = (px - u_c) / u_r;
  float cr = cos(u_roll), sr = sin(u_roll);
  q = vec2(cr * q.x + sr * q.y, -sr * q.x + cr * q.y);          // the axis leaning in the frame
  float r2 = dot(q, q);
  float edge = 1.0 - smoothstep(0.985, 1.0, sqrt(r2));
  if (r2 > 1.0) { frag = vec4(0.0); return; }
  vec3 n = vec3(q.x, -q.y, sqrt(max(1.0 - r2, 0.0)));
  float ct = cos(u_tilt), st = sin(u_tilt);
  n = vec3(n.x, ct * n.y - st * n.z, st * n.y + ct * n.z);
  float lon = atan(n.x, n.z) + u_rot;
  float lat = asin(clamp(n.y, -1.0, 1.0));
  vec2 uv = vec2(fract(lon / 6.2831853 + 0.5), 0.5 - lat / 3.14159265);
  vec3 c = texture(u_map, uv).rgb;
  // lantern: light glows from inside -> brighter at centre, warm falloff at the rim
  float mu = sqrt(max(1.0 - r2, 0.0));
  vec3 warm = vec3(1.0, 0.78, 0.45);
  c = c * mix(0.55, 1.15, pow(mu, 0.6)) + warm * u_glow * pow(mu, 2.0) * 0.35;
  // bamboo ribs: horizontal hoops of the paper lantern
  float hoop = abs(fract(lat / 3.14159265 * u_ribs + 0.5) - 0.5);
  float ribline = 1.0 - smoothstep(0.0, 0.035, hoop);
  c = mix(c, u_rib.rgb, ribline * u_rib.a * mix(0.4, 1.0, mu));
  // rim darkening
  c *= mix(0.65, 1.0, smoothstep(0.0, 0.35, mu)) * u_bright;
  frag = vec4(c * edge * u_alpha, edge * u_alpha);
}
"""


_SKY_FS = """
#version 430
uniform vec2 u_res; uniform sampler2D u_sky; uniform mat3 u_rot; uniform float u_f; uniform float u_gain;
uniform float u_time; uniform float u_stars; uniform vec3 u_band; uniform vec2 u_off;
out vec4 frag;
const float PI = 3.14159265;
vec3 h33(vec3 p){ p = fract(p * vec3(0.1031, 0.1030, 0.0973)); p += dot(p, p.yxz + 33.33);
  return fract((p.xxy + p.yxx) * p.zyx); }
vec4 h34(vec3 p){ vec4 q = fract(vec4(p.xyzx) * vec4(0.1031, 0.1030, 0.0973, 0.1099)); q += dot(q, q.wzxy + 33.33);
  return fract((q.xxyz + q.yzzw) * q.zywx); }
vec3 starfield(vec3 d, mat3 R, float scale, float dens, float px){
  vec3 dl = R * d;
  vec3 p = dl * scale, c = floor(p), acc = vec3(0.0);
  for (int i = -1; i <= 1; i++) for (int j = -1; j <= 1; j++) for (int k = -1; k <= 1; k++){
    vec3 cell = c + vec3(i, j, k);
    vec4 hh = h34(cell + 0.5);
    if (hh.x > dens) continue;
    vec3 sd = normalize(cell + h33(cell * 1.37 + 7.1));
    float ang = length(sd - dl);
    float b = pow(hh.y, 6.0);
    float sz = px * (0.7 + 1.4 * b);
    float tw = 0.72 + 0.28 * sin(u_time * (1.5 + 4.0 * hh.z) + 6.283 * hh.w);
    vec3 tint = mix(vec3(1.0, 0.86, 0.7), vec3(0.8, 0.86, 1.0), hh.z);
    acc += tint * (0.1 + 1.7 * b) * tw * exp(-ang * ang / (sz * sz));
  }
  return acc;
}
const mat3 R1 = mat3(0.36, 0.48, -0.8, -0.8, 0.6, 0.0, 0.48, 0.64, 0.6);
const mat3 R2 = mat3(0.6, 0.0, 0.8, 0.64, 0.6, -0.48, -0.48, 0.8, 0.36);
void main(){
  vec2 px = vec2(gl_FragCoord.x, u_res.y - gl_FragCoord.y);
  vec2 q = px - 0.5 * u_res - u_off;
  vec3 d = normalize(u_rot * normalize(vec3(q.x, -q.y, -u_f)));
  float az = atan(d.x, d.y);
  float el = asin(clamp(d.z, -1.0, 1.0));
  vec3 c = textureLod(u_sky, vec2(az / (2.0 * PI) + 0.5, 0.5 - el / PI), 0.0).rgb * u_gain;
  float up = smoothstep(-0.02, 0.12, d.z);
  float band = exp(-pow(dot(d, u_band) / 0.12, 2.0));
  float pix = 1.0 / u_f;
  c += u_stars * up * starfield(d, R1, 190.0, 0.04, pix);
  c += u_stars * up * band * 0.4 * starfield(d, R2, 360.0, 0.07, pix * 0.8);
  frag = vec4(c, 1.0);
}
"""


class Tex:
    def __init__(self, tex, w, h):
        self.tex, self.w, self.h = tex, w, h

    @property
    def aspect(self):
        return self.w / self.h


class Cam:
    def __init__(self, x=0.0, y=0.0, z=-FOCAL, roll=0.0, f=FOCAL, shift=(0.0, 0.0)):
        self.x, self.y, self.z, self.roll, self.f = x, y, z, roll, f
        self.shift = shift          # screen-space lens shift in pixels (+y moves the world down: looking up)

    def scale_at(self, z):
        """Screen pixels per world unit for a plane at depth z."""
        return self.f / max(z - self.z, 1e-3)


def premultiply(rgba):
    a = rgba[..., 3:4].astype(np.float32) / 255.0
    out = rgba.copy()
    out[..., :3] = (rgba[..., :3].astype(np.float32) * a + 0.5).astype(np.uint8)
    return out


def load_rgba(path):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise FileNotFoundError(path)
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGRA)
    elif im.shape[2] == 3:
        im = cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
    return cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA)


BLENDS = {
    "normal": (moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA, moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA),
    "add": (moderngl.ONE, moderngl.ONE, moderngl.ZERO, moderngl.ONE),
    "screen": (moderngl.ONE, moderngl.ONE_MINUS_SRC_COLOR, moderngl.ZERO, moderngl.ONE),
    "multiply": (moderngl.DST_COLOR, moderngl.ONE_MINUS_SRC_ALPHA, moderngl.ZERO, moderngl.ONE),
    "erase": (moderngl.ZERO, moderngl.ONE_MINUS_SRC_ALPHA, moderngl.ZERO, moderngl.ONE_MINUS_SRC_ALPHA),
    "mask": (moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA, moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA),
}

INST_FMT = "3f 2f 3f 4f 4f 3f/i"
INST_ATTRS = ("i_pos", "i_size", "i_rot", "i_uv", "i_col", "i_add")
INST_FLOATS = 19
MAX_INST = 30000


class Engine:
    def __init__(self, w=W, h=H, paper=None):
        self.w, self.h = w, h
        self.ctx = moderngl.create_standalone_context(require=430)
        ctx = self.ctx
        self.p_sprite = ctx.program(vertex_shader=_SPRITE_VS, fragment_shader=_SPRITE_FS)
        self.p_shape = ctx.program(vertex_shader=_FS_QUAD_VS, fragment_shader=_SHAPE_FS)
        self.p_rays = ctx.program(vertex_shader=_FS_QUAD_VS, fragment_shader=_RAYS_FS)
        self.p_grad = ctx.program(vertex_shader=_FS_QUAD_VS, fragment_shader=_GRAD_FS)
        self.p_bright = ctx.program(vertex_shader=_FS_QUAD_VS, fragment_shader=_BRIGHT_FS)
        self.p_blur = ctx.program(vertex_shader=_FS_QUAD_VS, fragment_shader=_BLUR_FS)
        self.p_trans = ctx.program(vertex_shader=_FS_QUAD_VS, fragment_shader=_TRANS_FS)
        self.p_post = ctx.program(vertex_shader=_FS_QUAD_VS, fragment_shader=_POST_FS)
        self.p_globe = ctx.program(vertex_shader=_FS_QUAD_VS, fragment_shader=_GLOBE_FS)
        self.p_sky = ctx.program(vertex_shader=_FS_QUAD_VS, fragment_shader=_SKY_FS)
        self.p_acc = ctx.program(vertex_shader=_FS_QUAD_VS, fragment_shader=_ACC_FS)

        fsq = np.array([-1, -1, 1, -1, -1, 1, 1, 1], "f4")
        self.fsq_vbo = ctx.buffer(fsq.tobytes())
        self.fsq = {p: ctx.vertex_array(p, [(self.fsq_vbo, "2f", "v_pos")])
                    for p in (self.p_shape, self.p_rays, self.p_grad, self.p_bright, self.p_blur, self.p_trans, self.p_post,
                              self.p_globe, self.p_sky, self.p_acc)}

        self.inst_buf = ctx.buffer(reserve=MAX_INST * INST_FLOATS * 4, dynamic=True)
        self.vao_quad = self._grid_vao(1)
        self.vao_grid = self._grid_vao(24)

        mk = lambda ww, hh, comp=4, dt="f2": ctx.framebuffer(color_attachments=[ctx.texture((ww, hh), comp, dtype=dt)])
        self.fbo_shot = [mk(w, h), mk(w, h)]
        self.fbo_comp = mk(w, h)
        self.fbo_mask = mk(w, h, 4, "f1")
        self.fbo_b1 = mk(w // 2, h // 2)
        self.fbo_b2 = mk(w // 4, h // 4)
        self.fbo_b3 = mk(w // 4, h // 4)
        self.fbo_out = mk(w, h, 4, "f1")
        self.fbo_acc = mk(w, h, 4, "f4")                     # (v28: sub-frame motion blur)
        for f in self.fbo_shot + [self.fbo_comp, self.fbo_b1, self.fbo_b2, self.fbo_b3]:
            f.color_attachments[0].filter = (moderngl.LINEAR, moderngl.LINEAR)
            f.color_attachments[0].repeat_x = False
            f.color_attachments[0].repeat_y = False
        self.cache = {}
        self.white = self.texture_from_array(np.full((4, 4, 4), 255, np.uint8), key="__white", mip=False)
        self.paper = self.texture_from_array(paper if paper is not None else np.full((8, 8, 4), 255, np.uint8),
                                             key="__paper", mip=False, premul=False)
        self.paper.tex.repeat_x = True
        self.paper.tex.repeat_y = True
        self.target = None
        self.cam = Cam()
        self.time = 0.0
        self.mask_mode = 0
        ctx.enable(moderngl.BLEND)

    # ------------------------------------------------------------------ resources
    def _grid_vao(self, n):
        g = np.linspace(0, 1, n + 1, dtype=np.float32)
        uu, vv = np.meshgrid(g, g)
        verts = np.stack([uu.ravel() - 0.5, vv.ravel() - 0.5, uu.ravel(), vv.ravel()], 1).astype("f4")
        idx = []
        for j in range(n):
            for i in range(n):
                a = j * (n + 1) + i
                idx += [a, a + 1, a + n + 1, a + 1, a + n + 2, a + n + 1]
        vbo = self.ctx.buffer(verts.tobytes())
        ibo = self.ctx.buffer(np.array(idx, "i4").tobytes())
        return self.ctx.vertex_array(self.p_sprite, [(vbo, "2f 2f", "v_corner", "v_uvbase"),
                                                     (self.inst_buf, INST_FMT, *INST_ATTRS)], index_buffer=ibo)

    def texture_from_array(self, rgba, key=None, mip=True, premul=True):
        if key is not None and key in self.cache:
            return self.cache[key]
        if premul:
            rgba = premultiply(rgba)
        h, w = rgba.shape[:2]
        t = self.ctx.texture((w, h), 4, np.ascontiguousarray(rgba).tobytes(), dtype="f1")
        if mip:
            t.build_mipmaps()
            t.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
            t.anisotropy = 16.0
        else:
            t.filter = (moderngl.LINEAR, moderngl.LINEAR)
        t.repeat_x = False
        t.repeat_y = False
        tx = Tex(t, w, h)
        if key is not None:
            self.cache[key] = tx
        return tx

    def tex(self, path):
        if path not in self.cache:
            self.cache[path] = self.texture_from_array(load_rgba(path), key=None)
        return self.cache[path]

    def update_texture(self, key, rgba, premul=True):
        """Re-upload a dynamic texture of fixed size (created on first call)."""
        if premul:
            rgba = premultiply(rgba)
        h, w = rgba.shape[:2]
        tx = self.cache.get(key)
        if tx is None or tx.w != w or tx.h != h:
            if tx is not None:
                tx.tex.release()
            t = self.ctx.texture((w, h), 4, dtype="f1")
            t.filter = (moderngl.LINEAR, moderngl.LINEAR)
            t.repeat_x = t.repeat_y = False
            tx = Tex(t, w, h)
            self.cache[key] = tx
        tx.tex.write(np.ascontiguousarray(rgba).tobytes())
        return tx

    def drop_cache(self, keep=()):
        for k in list(self.cache):
            if k.startswith("__") or k in keep:
                continue
            self.cache[k].tex.release()
            del self.cache[k]

    # ------------------------------------------------------------------ targets
    def begin(self, fbo, clear=(0, 0, 0, 1)):
        self.target = fbo
        fbo.use()
        self.ctx.viewport = (0, 0, fbo.width, fbo.height)
        if clear is not None:
            fbo.clear(*clear)

    def _blend(self, mode):
        self.ctx.blend_func = BLENDS[mode]

    @staticmethod
    def _u(prog, name, val):
        try:
            prog[name].value = val
        except KeyError:
            pass

    # ------------------------------------------------------------------ sprites
    def sprites(self, tex, inst, blend="normal", cam=None, screen=False, mode=0, warp=None, warp2=None,
                rim=None, rim_off=(0.004, 0.004), cut=None, grid=False, mask=0):
        """inst: (N,19) float32 array [x,y,z, w,h, rx,ry,rz, u0,v0,u1,v1, r,g,b,a, ar,ag,ab]."""
        n = len(inst)
        if n == 0:
            return
        p = self.p_sprite
        cam = cam or self.cam
        u = self._u
        u(p, "u_cam", (cam.x, cam.y, cam.z))
        u(p, "u_roll", cam.roll)
        u(p, "u_f", cam.f)
        u(p, "u_shift", tuple(map(float, getattr(cam, "shift", (0.0, 0.0)))))
        u(p, "u_screen", 1 if screen else 0)
        u(p, "u_res", (float(self.target.width), float(self.target.height)))
        u(p, "u_warp", tuple(warp) if warp else (0.0, 0.0, 0.0, 0.0))
        u(p, "u_warp2", tuple(warp2) if warp2 else (0.0, 0.0, 0.0, 0.0))
        u(p, "u_time", self.time)
        u(p, "u_mode", mode)
        u(p, "u_rim", tuple(rim) if rim else (1.0, 1.0, 1.0, 0.0))
        u(p, "u_rimoff", tuple(rim_off))
        u(p, "u_cut", tuple(cut) if cut else (0.0, 0.0, 0.0, 0.0))
        u(p, "u_usemask", mask)
        tex.tex.use(0)
        u(p, "u_tex", 0)
        if mask:
            self.fbo_mask.color_attachments[0].use(1)
            u(p, "u_mask", 1)
        self._blend(blend)
        vao = self.vao_grid if (grid or warp or warp2) else self.vao_quad
        for s in range(0, n, MAX_INST):
            chunk = np.ascontiguousarray(inst[s:s + MAX_INST], dtype="f4")
            self.inst_buf.write(chunk.tobytes())
            vao.render(moderngl.TRIANGLES, instances=len(chunk))

    @staticmethod
    def inst(x, y, z, w, h, rot=0.0, rx=0.0, ry=0.0, uv=(0, 0, 1, 1), color=(1, 1, 1, 1), add=(0, 0, 0)):
        return np.array([x, y, z, w, h, rx, ry, rot, *uv, *color, *add], "f4")

    def image(self, tex, x=0.0, y=0.0, z=0.0, w=None, h=None, scale=1.0, rot=0.0, rx=0.0, ry=0.0,
              alpha=1.0, color=(1, 1, 1), add=(0, 0, 0), uv=(0, 0, 1, 1), anchor=(0.5, 0.5), **kw):
        """Draw one textured quad. In world space by default; pass screen=True for pixel space."""
        if w is None and h is None:
            w, h = tex.w * scale, tex.h * scale
        elif w is None:
            w = h * tex.aspect
        elif h is None:
            h = w / tex.aspect
        # anchor offset (in local, unrotated space)
        ox, oy = (0.5 - anchor[0]) * w, (0.5 - anchor[1]) * h
        if ox or oy:
            c, s = math.cos(rot), math.sin(rot)
            x, y = x + c * ox - s * oy, y + s * ox + c * oy
        self.sprites(tex, self.inst(x, y, z, w, h, rot, rx, ry, uv, (*color, alpha), add)[None], **kw)

    def layer(self, tex, z=0.0, cover=1.0, x=0.0, y=0.0, alpha=1.0, ref_cam=None, **kw):
        """Fill the screen with tex as a plane at depth z (sized to cover the frame from ref_cam * cover)."""
        rc = ref_cam or Cam()
        s = rc.scale_at(z)
        need_w, need_h = self.w / s * cover, self.h / s * cover
        if need_w / need_h > tex.aspect:
            w, h = need_w, need_w / tex.aspect
        else:
            w, h = need_h * tex.aspect, need_h
        self.image(tex, x, y, z, w, h, alpha=alpha, **kw)

    # ------------------------------------------------------------------ procedural
    def _fs(self, prog):
        self.fsq[prog].render(moderngl.TRIANGLE_STRIP)

    def shape(self, kind, c, p, color, soft=0.0, arc=(0.0, 6.2832), rough=0.0, seed=0.0, rot=0.0, blend="normal"):
        """Screen-space SDF shape. kind: disc|ring|rect|seg. p: params (see shader)."""
        pr = self.p_shape
        u = self._u
        u(pr, "u_res", (float(self.target.width), float(self.target.height)))
        u(pr, "u_type", {"disc": 0, "ring": 1, "rect": 2, "seg": 3}[kind])
        u(pr, "u_c", tuple(map(float, c)))
        pp = list(p) + [0.0] * (4 - len(p))
        u(pr, "u_p", tuple(map(float, pp)))
        u(pr, "u_col", tuple(map(float, color)))
        u(pr, "u_soft", float(soft))
        u(pr, "u_arc", tuple(map(float, arc)))
        u(pr, "u_rough", float(rough))
        u(pr, "u_seed", float(seed))
        u(pr, "u_rot", float(rot))
        self._blend(blend)
        self._fs(pr)

    def rays(self, c, n, color, rot=0.0, width=0.3, rad=(0, 2000), soft=0.08, blend="add"):
        pr = self.p_rays
        u = self._u
        u(pr, "u_res", (float(self.target.width), float(self.target.height)))
        u(pr, "u_c", tuple(map(float, c)))
        u(pr, "u_n", float(n))
        u(pr, "u_rot", float(rot))
        u(pr, "u_width", float(width))
        u(pr, "u_rad", tuple(map(float, rad)))
        u(pr, "u_col", tuple(map(float, color)))
        u(pr, "u_soft", float(soft))
        self._blend(blend)
        self._fs(pr)

    def gradient(self, a, b, c0, c1, c2=None, pos=(0.0, 0.5, 1.0), radial=False, blend="normal"):
        pr = self.p_grad
        u = self._u
        u(pr, "u_res", (float(self.target.width), float(self.target.height)))
        u(pr, "u_type", 1 if radial else 0)
        u(pr, "u_a", tuple(map(float, a)))
        u(pr, "u_b", tuple(map(float, b)))
        c2 = c2 if c2 is not None else c1
        if len(pos) == 2:
            pos = (pos[0], pos[1], 1.0)
        u(pr, "u_c0", tuple(map(float, c0)))
        u(pr, "u_c1", tuple(map(float, c1)))
        u(pr, "u_c2", tuple(map(float, c2)))
        u(pr, "u_pos", tuple(map(float, pos)))
        self._blend(blend)
        self._fs(pr)

    def fill(self, color, blend="normal"):
        self.gradient((0, 0), (0, self.h), color, color, color, blend=blend)

    # ------------------------------------------------------------------ masks
    def mask_begin(self, clear=0.0):
        """Subsequent draws go into the mask buffer (alpha used). Call mask_end() to return."""
        self._saved = self.target
        self.begin(self.fbo_mask, clear=(0, 0, 0, clear))

    def mask_end(self):
        self.begin(self._saved, clear=None)

    # ------------------------------------------------------------------ compositing
    def globe(self, tex, c, r, rot=0.0, tilt=0.25, glow=1.0, rib=(0.35, 0.12, 0.06, 0.55), ribs=9.0, alpha=1.0,
              bright=0.8, roll=0.0):
        """Rotating paper-lantern globe in screen space (equirect map texture)."""
        pr = self.p_globe
        u = self._u
        tex.tex.repeat_x = True
        tex.tex.use(0)
        u(pr, "u_map", 0)
        u(pr, "u_res", (float(self.target.width), float(self.target.height)))
        u(pr, "u_c", tuple(map(float, c)))
        u(pr, "u_r", float(r))
        u(pr, "u_rot", float(rot))
        u(pr, "u_tilt", float(tilt))
        u(pr, "u_glow", float(glow))
        u(pr, "u_rib", tuple(map(float, rib)))
        u(pr, "u_ribs", float(ribs))
        u(pr, "u_alpha", float(alpha))
        u(pr, "u_bright", float(bright))
        u(pr, "u_roll", float(roll))
        self._blend("normal")
        self._fs(pr)

    def sky(self, tex, rot, f, gain=1.0, stars=1.0, t=0.0, band=(0.82, -0.25, 0.52), off=(0.0, 0.0)):
        """Equirect night sky seen through a camera: rot = 3x3 camera-to-world matrix (columns right, up, back;
        world x right, y forward, z up), f = focal length in pixels. Adds procedural twinkling stars."""
        pr = self.p_sky
        u = self._u
        tex.tex.repeat_x = True
        tex.tex.use(0)
        u(pr, "u_sky", 0)
        u(pr, "u_res", (float(self.target.width), float(self.target.height)))
        u(pr, "u_rot", tuple(float(v) for v in np.asarray(rot, np.float64).flatten(order="F")))
        u(pr, "u_f", float(f))
        u(pr, "u_gain", float(gain))
        u(pr, "u_stars", float(stars))
        u(pr, "u_time", float(t))
        u(pr, "u_off", (float(off[0]), float(off[1])))
        b = np.asarray(band, np.float64)
        u(pr, "u_band", tuple(float(v) for v in b / np.linalg.norm(b)))
        self._blend("normal")
        self._fs(pr)

    def accumulate(self, src, dst, w, clear=False, blend=True):
        """dst += src * w (blend=False: dst = src * w) - the sub-frames of a motion-blurred frame."""
        self.begin(dst, clear=(0, 0, 0, 0) if clear else None)
        src.color_attachments[0].use(0)
        self._u(self.p_acc, "u_src", 0)
        self._u(self.p_acc, "u_res", (float(self.w), float(self.h)))
        self._u(self.p_acc, "u_w", float(w))
        if blend:
            self.ctx.blend_func = (moderngl.ONE, moderngl.ONE, moderngl.ONE, moderngl.ONE)
        else:
            self.ctx.disable(moderngl.BLEND)
        self._fs(self.p_acc)
        self.ctx.enable(moderngl.BLEND)
        self._blend("normal")

    def transition(self, mode, p, q=(0, 0, 0, 0), col=(1, 1, 1, 1)):
        """Blend fbo_shot[0] (A) -> fbo_shot[1] (B) into fbo_comp."""
        self.begin(self.fbo_comp, clear=(0, 0, 0, 1))
        pr = self.p_trans
        self.fbo_shot[0].color_attachments[0].use(0)
        self.fbo_shot[1].color_attachments[0].use(1)
        u = self._u
        u(pr, "u_a", 0)
        u(pr, "u_b", 1)
        u(pr, "u_res", (float(self.w), float(self.h)))
        u(pr, "u_mode", int(mode))
        u(pr, "u_p", float(p))
        u(pr, "u_q", tuple(map(float, q)))
        u(pr, "u_col", tuple(map(float, col)))
        self.ctx.disable(moderngl.BLEND)
        self._fs(pr)
        self.ctx.enable(moderngl.BLEND)
        return self.fbo_comp

    def post(self, src, grade=None, t=0.0):
        g = dict(bloom=0.35, thr=0.75, lift=(0, 0, 0), gamma=(1, 1, 1), gain=(1, 1, 1), sat=1.0, exposure=1.0,
                 grain=0.035, vig=0.25, paper=0.55, flash=(1, 1, 1, 0), ca=0.0, fade=1.0, zb=0.0, zbc=(0.5, 0.5),
                 xs=1.0, xr=0.0, xo=(0.0, 0.0), mb=(0.0, 0.0), rb=(0.0, 0.5, 0.5))
        if grade:
            g.update(grade)
        ctx = self.ctx
        ctx.disable(moderngl.BLEND)
        srct = src.color_attachments[0]
        # bloom: bright pass at 1/2, blur at 1/4
        self.begin(self.fbo_b1, clear=None)
        srct.use(0)
        self._u(self.p_bright, "u_src", 0)
        self._u(self.p_bright, "u_res", (float(self.fbo_b1.width), float(self.fbo_b1.height)))
        self._u(self.p_bright, "u_thr", float(g["thr"]))
        self._fs(self.p_bright)
        self.begin(self.fbo_b2, clear=None)
        self.fbo_b1.color_attachments[0].use(0)
        self._u(self.p_blur, "u_src", 0)
        self._u(self.p_blur, "u_res", (float(self.fbo_b2.width), float(self.fbo_b2.height)))
        for _ in range(2):
            self.begin(self.fbo_b3, clear=None)
            self.fbo_b2.color_attachments[0].use(0) if _ else self.fbo_b1.color_attachments[0].use(0)
            self._u(self.p_blur, "u_dir", (1.0, 0.0))
            self._fs(self.p_blur)
            self.begin(self.fbo_b2, clear=None)
            self.fbo_b3.color_attachments[0].use(0)
            self._u(self.p_blur, "u_dir", (0.0, 1.0))
            self._fs(self.p_blur)
        # final
        self.begin(self.fbo_out, clear=None)
        pr = self.p_post
        srct.use(0)
        self.fbo_b2.color_attachments[0].use(1)
        self.paper.tex.use(2)
        u = self._u
        u(pr, "u_scene", 0)
        u(pr, "u_bloom", 1)
        u(pr, "u_paper", 2)
        u(pr, "u_res", (float(self.w), float(self.h)))
        u(pr, "u_time", float(t))
        u(pr, "u_bloom_amt", float(g["bloom"]))
        u(pr, "u_lift", tuple(map(float, g["lift"])))
        u(pr, "u_gamma", tuple(map(float, g["gamma"])))
        u(pr, "u_gain", tuple(map(float, g["gain"])))
        u(pr, "u_sat", float(g["sat"]))
        u(pr, "u_exposure", float(g["exposure"]))
        u(pr, "u_grain", float(g["grain"]))
        u(pr, "u_vig", float(g["vig"]))
        u(pr, "u_paper_amt", float(g["paper"]))
        u(pr, "u_flash", tuple(map(float, g["flash"])))
        u(pr, "u_ca", float(g["ca"]))
        u(pr, "u_fade", float(g["fade"]))
        u(pr, "u_zb", float(g["zb"]))
        u(pr, "u_zbc", tuple(map(float, g["zbc"])))
        u(pr, "u_xs", float(g["xs"]))
        u(pr, "u_xr", float(g["xr"]))
        u(pr, "u_xo", tuple(map(float, g["xo"])))
        u(pr, "u_mb", tuple(map(float, g["mb"])))
        u(pr, "u_rb", tuple(map(float, g["rb"])))
        ox = (math.floor(t * 12) * 0.137) % 1.0
        u(pr, "u_paper_off", (ox * 0.002, ox * 0.0013))
        self._fs(pr)
        ctx.enable(moderngl.BLEND)
        return self.fbo_out

    def read(self, fbo=None):
        fbo = fbo or self.fbo_out
        data = fbo.read(components=3, dtype="f1")
        return np.frombuffer(data, np.uint8).reshape(fbo.height, fbo.width, 3)[::-1]
