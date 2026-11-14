"""Public OBJ geometry diagnostics only; never registers a mesh or reads recordings."""
from pathlib import Path
import sys, json, hashlib, math

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/_sonar_audit_deps'))
import numpy as np
from PIL import Image, ImageDraw

ASSETS = ROOT / 'related_work/sonar-projection-audit-assets/data_export_3dmodels/3d_models'
OUT = ROOT / 'DataSet/sonar_registration_methods/anchors'
MODELS = [('100lbs', .737, .208), ('incindiary', .442, .127), ('mortar_shell', .580, .120)]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def parse_obj(path):
    vertices, colors, faces, refs = [], [], [], []
    for line in path.read_text(encoding='utf-8').splitlines():
        s = line.split()
        if not s:
            continue
        if s[0] == 'v':
            vertices.append(list(map(float, s[1:4])))
            colors.append(list(map(float, s[4:7])) if len(s) >= 7 else [.45, .4, .3])
        elif s[0] == 'f':
            ids = [int(x.split('/')[0]) for x in s[1:]]
            ids = [i - 1 if i > 0 else len(vertices) + i for i in ids]
            faces.extend([[ids[0], ids[i], ids[i + 1]] for i in range(1, len(ids) - 1)])
        elif s[0] == 'mtllib':
            refs.append(s[1])
    return np.array(vertices), np.array(colors), np.array(faces), refs


def axes_from_cov(cov):
    values, axes = np.linalg.eigh(cov)
    order = np.argsort(values)[::-1]
    values, axes = values[order], axes[:, order].T
    for i in (0, 1):
        if axes[i, np.argmax(np.abs(axes[i]))] < 0:
            axes[i] *= -1
    axes[2] = np.cross(axes[0], axes[1])
    return values, axes


def geometry(v, faces):
    tri = v[faces]
    areas = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1) / 2
    area = areas.sum()
    center = (tri.mean(1) * areas[:, None]).sum(0) / area
    # Exact first/second moments for a uniform distribution over each triangle.
    summed = tri.sum(1)
    second = (np.einsum('nki,nkj->nij', tri, tri) + np.einsum('ni,nj->nij', summed, summed)) / 12
    cov = (second * areas[:, None, None]).sum(0) / area - np.outer(center, center)
    values, axes = axes_from_cov(cov)
    vertex_values, vertex_axes = axes_from_cov(np.cov(v.T, bias=True))
    local = (v - center) @ axes.T
    lo, hi = local.min(0), local.max(0)
    quantiles = np.quantile(local[:, 0], [.005, .01, .99, .995])
    profile = []
    edges = np.linspace(lo[0], hi[0], 41)
    for i, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
        group = local[(local[:, 0] >= a) & ((local[:, 0] < b) if i < 39 else (local[:, 0] <= b))]
        if not len(group):
            continue
        radius = np.linalg.norm(group[:, 1:], axis=1)
        profile.append(dict(axial_fraction=(i + .5) / 40, vertices=len(group),
                            radius_q50=float(np.quantile(radius, .5)), radius_q95=float(np.quantile(radius, .95)),
                            radius_max=float(radius.max()), transverse_span=np.ptp(group[:, 1:], axis=0).tolist()))
    parent = list(range(len(v)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a, b, c in faces.tolist():
        pa, pb, pc = find(a), find(b), find(c)
        parent[pb] = pa
        parent[pc] = pa
    labels = np.array([find(i) for i in range(len(v))])
    counts = sorted([(int(k), int(n)) for k, n in zip(*np.unique(labels, return_counts=True))], key=lambda x: -x[1])
    top = []
    for k, n in counts[:8]:
        idx = np.where(labels == k)[0]
        top.append(dict(vertices=n, fraction=n / len(v), raw_bounds=[v[idx].min(0).tolist(), v[idx].max(0).tolist()]))
    return local, dict(area_centroid_raw=center.tolist(), area_pca_axes_rows=axes.tolist(),
                      area_pca_eigenvalues=values.tolist(), vertex_pca_eigenvalues=vertex_values.tolist(),
                      area_to_vertex_axis_angle_deg=[float(np.degrees(np.arccos(np.clip(abs(a @ b), 0, 1)))) for a, b in zip(axes, vertex_axes)],
                      area_pca_extent=np.ptp(local, axis=0).tolist(), area_pca_bounds=[lo.tolist(), hi.tolist()],
                      axial_vertex_quantiles_005_01_99_995=quantiles.tolist(),
                      components_count=len(counts), largest_components=top, profile=profile,
                      transverse_eigenvalue_ratio=float(values[1] / values[2]),
                      axial_sign_convention='Largest absolute raw-axis component positive; NOT semantic head/tail or world orientation',
                      endpoints_note='Extrema and quantiles are geometric diagnostics, not physical target-origin definitions')


def scatter_panel(canvas, points, colors, axes, origin, label):
    x0, y0 = origin
    draw = ImageDraw.Draw(canvas)
    w, h = 530, 285
    draw.text((x0 + 8, y0 + 4), label, fill='black')
    xy = points[:, axes[:2]]
    extent = np.ptp(xy, axis=0)
    factor = min((w - 55) / max(extent[0], 1e-9), (h - 60) / max(extent[1], 1e-9))
    midpoint = (xy.max(0) + xy.min(0)) / 2
    px = np.rint((xy[:, 0] - midpoint[0]) * factor + w / 2).astype(int)
    py = np.rint(-(xy[:, 1] - midpoint[1]) * factor + h / 2 + 8).astype(int)
    # Vertex z-buffer preview, explicitly not a calibrated or acoustic rendering.
    order = np.argsort(points[:, axes[2]], kind='stable')
    rgb = np.clip(np.rint(colors * 255 * 1.65), 0, 255).astype(np.uint8)
    panel = np.full((h, w, 3), 244, np.uint8)
    inside = (px >= 0) & (px < w) & (py >= 23) & (py < h - 18)
    order = order[inside[order]]
    for k in order:
        panel[py[k], px[k]] = rgb[k]
    canvas.paste(Image.fromarray(panel), (x0, y0 + 23))
    draw.text((x0 + 8, y0 + h + 9), f'x={axes[0]} increases right; y={axes[1]} increases up; view +{axes[2]}', fill=(65, 65, 65))


def render(name, raw, local, colors, info, out):
    im = Image.new('RGB', (1610, 790), 'white')
    d = ImageDraw.Draw(im)
    d.text((12, 9), f'{name}: raw mesh and area-weighted PCA. Vertex colors x1.65; no world registration.', fill='black')
    for j, axis in enumerate([(0, 1, 2), (0, 2, 1), (1, 2, 0)]):
        scatter_panel(im, raw, colors, axis, (j * 535, 35), f'RAW axes {axis[0]}/{axis[1]}')
        scatter_panel(im, local, colors, axis, (j * 535, 390), f'AREA PCA axes {axis[0]}/{axis[1]} (sign arbitrary)')
    d.text((12, 755), 'Photogrammetry object-only diagnostic. No scale bar, target origin or world axis is inferred from this preview.', fill='black')
    im.save(out / (name + '-geometry.png'))
    profile = info['profile']
    chart = Image.new('RGB', (1000, 380), 'white')
    d = ImageDraw.Draw(chart)
    d.text((20, 12), f'{name}: transverse radius along area-PCA axis 0; raw OBJ units', fill='black')
    d.line((60, 60, 60, 320, 960, 320), fill='black')
    maxr = max(p['radius_max'] for p in profile)
    for key, color in [('radius_q50', '#3377aa'), ('radius_q95', '#ee8800'), ('radius_max', '#555555')]:
        coords = [(60 + p['axial_fraction'] * 900, 320 - p[key] / maxr * 250) for p in profile]
        d.line(coords, fill=color, width=2)
        d.text((65 + 270 * ['radius_q50', 'radius_q95', 'radius_max'].index(key), 345), key, fill=color)
    d.text((5, 42), f'{maxr:.3f}', fill='black')
    d.text((60, 325), '0% (lower coordinate end)', fill='black')
    d.text((780, 325), '100% (higher end)', fill='black')
    chart.save(out / (name + '-profile.png'))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result_file = OUT / 'geometry.json'
    if result_file.exists():
        raise RuntimeError('Preserve existing diagnostics; do not overwrite a completed run')
    inputs = [ROOT / 'experiment/sonar-registration-methods-plan.md', Path(__file__),
              ROOT / 'related_work/model-registration-sources/historical-README.md',
              ROOT / 'related_work/model-registration-sources/object-notes-9a0ebad3.md']
    inputs += [ASSETS / (name + suffix) for name, _, _ in MODELS for suffix in ['.obj', '.mtl', '.jpg']]
    hashes = {str(p): sha(p) for p in inputs}
    results = []
    for name, length, diameter in MODELS:
        obj = ASSETS / (name + '.obj')
        v, colors, faces, refs = parse_obj(obj)
        assert len(v) and faces.min() >= 0 and faces.max() < len(v)
        local, info = geometry(v, faces)
        mtl = ASSETS / (name + '.mtl')
        textures = [line.split(maxsplit=1)[1] for line in mtl.read_text().splitlines() if line.startswith('map_Kd ')]
        info.update(model=name, vertices=len(v), triangles=len(faces),
                    nominal_length_m=length, nominal_diameter_m=diameter,
                    length_only_area_pca_scale=length / info['area_pca_extent'][0],
                    length_only_area_pca_transverse_span_m=(np.array(info['area_pca_extent'][1:]) * length / info['area_pca_extent'][0]).tolist(),
                    obj_mtllib=[dict(path=r, exists=(ASSETS / r).exists()) for r in refs],
                    mtl_map_Kd=[dict(path=r, exists=(ASSETS / r).exists()) for r in textures],
                    actual_named_texture=str(ASSETS / (name + '.jpg')),
                    rendering='Embedded OBJ vertex colors only; no guessed UV remap')
        render(name, v, local, colors, info, OUT)
        results.append(info)
    after = {str(p): sha(p) for p in inputs}
    assert hashes == after, 'Inputs changed during diagnostics'
    payload = dict(status='geometry diagnostics only; no mesh registration or GT generated', models=results,
                   hashes_before=hashes, hashes_after=after, inputs_unchanged=True,
                   recording_images_read=0, models_read=3, source_geometry_edited=False)
    result_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps([{k: m[k] for k in ['model','vertices','triangles','area_pca_extent','area_to_vertex_axis_angle_deg','transverse_eigenvalue_ratio','components_count','length_only_area_pca_transverse_span_m','obj_mtllib','mtl_map_Kd']} for m in results], indent=2))


if __name__ == '__main__':
    main()
