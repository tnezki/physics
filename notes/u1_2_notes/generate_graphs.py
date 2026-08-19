# =============================================================================
# graph_tool.py — AUTHORITATIVE SOURCE FOR ALL GRAPH STYLING AND BEHAVIOR
# =============================================================================
#
# DO NOT modify, refactor, restyle, simplify, optimize, or rewrite anything
# in this file. All styling decisions have been finalized here.
#
# TO USE THIS FILE FOR GRAPH GENERATION:
#   1. Copy this file in full as generate_graphs.py
#   2. Append graph-generation blocks below the final section marker
#   3. Never insert code into the middle of this file
#   4. Never override styling in graph-generation blocks
#
# FAIL THE TASK IF:
#   - Any existing line above the append section is modified
#   - Any graph is generated without using functions from this file
#   - Styling is manually overridden outside graph-generation blocks
#   - HTML, CSS, MathJax, or layout in the resource file is changed
#
# =============================================================================

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figures')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# SHARED UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _exit_arrows(ax, f, fprime, color, xmin, xmax, ymin, ymax):
    x = np.linspace(xmin, xmax, 2000)
    y = f(x)
    exit_points = []
    yl = f(xmin)
    if ymin <= yl <= ymax:
        exit_points.append((xmin, yl, -1, 'side'))
    yr = f(xmax)
    if ymin <= yr <= ymax:
        exit_points.append((xmax, yr, 1, 'side'))
    for edge_y, direction in [(ymin, -1), (ymax, 1)]:
        vals = y - edge_y
        for idx in np.where(np.diff(np.sign(vals)))[0]:
            xr = np.interp(0, [vals[idx], vals[idx+1]], [x[idx], x[idx+1]])
            exit_points.append((xr, edge_y, direction, 'topbot'))
    for (xe, ye, direction, edge) in exit_points:
        slope = fprime(xe)
        if abs(slope) < 0.001:
            continue
        if edge == 'topbot':
            dy_dir = float(direction)
            dx_dir = dy_dir / slope
        else:
            dx_dir = float(direction)
            dy_dir = slope * dx_dir
        mag = np.sqrt(dx_dir**2 + dy_dir**2)
        dx_dir /= mag
        dy_dir /= mag
        L = 0.45
        ax.annotate('', xy=(xe + dx_dir*L, ye + dy_dir*L),
                        xytext=(xe, ye),
                    arrowprops=dict(arrowstyle='-|>', color=color,
                                    lw=1.5, mutation_scale=12))


def _find_key_points(functions, xmin, xmax, ymin, ymax):
    key_points = []
    x_check = np.linspace(xmin, xmax, 2000)
    if len(functions) >= 2:
        for i in range(len(functions)):
            for j in range(i+1, len(functions)):
                try:
                    diff = functions[i]['expr'](x_check) - functions[j]['expr'](x_check)
                    for idx in np.where(np.diff(np.sign(diff)))[0]:
                        xr = np.interp(0, [diff[idx], diff[idx+1]],
                                          [x_check[idx], x_check[idx+1]])
                        yr = functions[i]['expr'](np.array([xr]))[0]
                        if ymin <= yr <= ymax:
                            key_points.append((xr, yr))
                except:
                    pass
    for fn in functions:
        try:
            dy = fn['deriv'](x_check)
            for idx in np.where(np.diff(np.sign(dy)))[0]:
                xv = np.interp(0, [dy[idx], dy[idx+1]],
                                  [x_check[idx], x_check[idx+1]])
                yv = fn['expr'](np.array([xv]))[0]
                if ymin <= yv <= ymax:
                    key_points.append((xv, yv))
        except:
            pass
    return key_points


def _score_corner(cx, cy, functions, key_points):
    score = 0
    for fn in functions:
        try:
            fy = fn['expr'](np.array([cx]))[0]
            score += abs(fy - cy) if np.isfinite(fy) else 20
        except:
            score += 20
    for (kx, ky) in key_points:
        dist = np.sqrt((cx - kx)**2 + (cy - ky)**2)
        if dist < 3:
            score -= (3 - dist) * 50
    return score


def _draw_legend(ax, functions, key_points, xmin, xmax, ymin, ymax):
    if len(functions) <= 1:
        return
    handles = [mpatches.Patch(color=fn['color'], label=fn['label'])
               for fn in functions if fn.get('label')]
    if not handles:
        return
    span_x = xmax - xmin
    span_y = ymax - ymin
    corners = {
        'upper right': (xmin + span_x*0.7, ymin + span_y*0.8),
        'upper left':  (xmin + span_x*0.2, ymin + span_y*0.8),
        'lower right': (xmin + span_x*0.7, ymin + span_y*0.15),
        'lower left':  (xmin + span_x*0.2, ymin + span_y*0.15),
    }
    best = max(corners, key=lambda c: _score_corner(*corners[c], functions, key_points))
    ax.legend(
        handles=handles,
        prop={'family': 'Times New Roman', 'size': 11, 'weight': 'bold'},
        loc=best,
        framealpha=0.9,
        edgecolor='#aaaaaa',
        handlelength=1.2,
        borderpad=0.5,
        labelspacing=0.3,
    )


def _nice_grid_step(data_range, max_lines=20):
    raw = data_range / max_lines
    mag = 10 ** np.floor(np.log10(max(raw, 1e-9)))
    for nice in [1, 2, 2.5, 5, 10]:
        step = nice * mag
        if data_range / step <= max_lines:
            return step
    return mag * 10


def _label_every(n_lines):
    if n_lines <= 10:
        return 2
    if n_lines <= 15:
        return 3
    return 5


def _fmt(v):
    return str(int(v)) if v == int(v) else f'{v:g}'


def _draw_axes_standard(ax, xmin, xmax, ymin, ymax):
    ax.spines['left'].set_position('zero')
    ax.spines['bottom'].set_position('zero')
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    for s in ['left', 'bottom']:
        ax.spines[s].set_linewidth(1.8)
        ax.spines[s].set_color('#222222')
    # set_bounds stops the spine at ±10.5 — xlim is set to ±10.5 in the
    # calling function so the spine exactly reaches the plot edge.
    # Arrow tips go to ±10.6 with annotation_clip=False so they render
    # outside the plot boundary and the spine cannot reach them.
    ax.spines['left'].set_bounds(ymin - 0.5, ymax + 0.5)
    ax.spines['bottom'].set_bounds(xmin - 0.5, xmax + 0.5)
    tri = dict(arrowstyle='-|>', color='#222222', lw=1.8, mutation_scale=14)
    ax.annotate('', xy=(xmax+0.6, 0), xytext=(xmax, 0),
                arrowprops=tri, annotation_clip=False)
    ax.annotate('', xy=(xmin-0.6, 0), xytext=(xmin, 0),
                arrowprops=tri, annotation_clip=False)
    ax.annotate('', xy=(0, ymax+0.6), xytext=(0, ymax),
                arrowprops=tri, annotation_clip=False)
    ax.annotate('', xy=(0, ymin-0.6), xytext=(0, ymin),
                arrowprops=tri, annotation_clip=False)
    ax.text(xmax+0.35, 0.4, 'x', fontsize=14, fontweight='bold',
            fontfamily='Times New Roman', ha='center', va='bottom')
    ax.text(0.35, ymax+0.35, 'y', fontsize=14, fontweight='bold',
            fontfamily='Times New Roman', ha='left', va='center')


# ─────────────────────────────────────────────────────────────────────────────
# TYPE 1 — STANDARD COORDINATE PLANE  (-10 to 10)
# Use for: algebra, parent functions, transformations, intersections.
#
# functions : list of dicts
#   'expr'  : lambda x: ...       the function
#   'deriv' : lambda x: ...       its derivative
#   'color' : 'steelblue'         steelblue | firebrick | darkorange
#   'label' : 'f'                 legend label — omit or None for 1 function
#
# title: LaTeX supported via r'$...$'  e.g.  r'$f(x)=x^2$'
# ─────────────────────────────────────────────────────────────────────────────

def make_standard_graph(ax, functions, title=''):
    XMIN, XMAX, YMIN, YMAX = -10, 10, -10, 10

    for fn in functions:
        f      = fn['expr']
        fprime = fn['deriv']
        color  = fn['color']
        label  = fn.get('label', None)
        x = np.linspace(XMIN, XMAX, 2000)
        y = f(x)
        mask = (y >= YMIN) & (y <= YMAX)
        segments = np.split(np.where(mask)[0],
                            np.where(np.diff(np.where(mask)[0]) > 5)[0] + 1)
        for seg in segments:
            if len(seg) > 1:
                ax.plot(x[seg], y[seg], color=color, linewidth=2, label=label)
                label = None
        _exit_arrows(ax, f, fprime, color, XMIN, XMAX, YMIN, YMAX)

    key_points = _find_key_points(functions, XMIN, XMAX, YMIN, YMAX)
    _draw_legend(ax, functions, key_points, XMIN, XMAX, YMIN, YMAX)

    ax.set_xlim(XMIN - 0.5, XMAX + 0.5)
    ax.set_ylim(YMIN - 0.5, YMAX + 0.5)
    ax.set_xticks(np.arange(XMIN, XMAX+1, 1), minor=True)
    ax.set_yticks(np.arange(YMIN, YMAX+1, 1), minor=True)
    ax.grid(True, which='minor', color='#aaaaaa', linewidth=0.6)
    ax.set_xticks([-10, -5, 5, 10])
    ax.set_yticks([-10, -5, 5, 10])
    ax.set_xticklabels(['-10','-5','5','10'],
                       fontfamily='Times New Roman', fontsize=11)
    ax.set_yticklabels(['-10','-5','5','10'],
                       fontfamily='Times New Roman', fontsize=11)
    ax.grid(True, which='major', color='#aaaaaa', linewidth=0.6)
    ax.tick_params(which='major', length=5, width=1.2, color='#222222')
    ax.tick_params(which='minor', length=2, width=0.8, color='#555555')
    _draw_axes_standard(ax, XMIN, XMAX, YMIN, YMAX)
    ax.set_title(title, fontfamily='Times New Roman', fontsize=12, pad=8)


# ─────────────────────────────────────────────────────────────────────────────
# TYPE 2 — CONTEXT / MODELING GRAPH
# Custom axis ranges for real-world problems. Q1 only (xmin/ymin typically 0).
# Max 20 grid lines per axis. Labels every 2nd-5th line automatically.
# Same grid darkness and weight as Type 1.
#
# functions : same structure as Type 1
# xmin/xmax/ymin/ymax : axis bounds
# xlabel/ylabel : axis label strings  e.g. 'Time (s)', 'Height (m)'
# title: LaTeX supported via r'$...$'
# ─────────────────────────────────────────────────────────────────────────────

def make_context_graph(ax, functions,
                       xmin, xmax, ymin, ymax,
                       xlabel='x', ylabel='y', title=''):
    x_range = xmax - xmin
    y_range = ymax - ymin

    x_step = _nice_grid_step(x_range)
    y_step = _nice_grid_step(y_range)
    x_ticks = np.arange(xmin, xmax + x_step*0.01, x_step)
    y_ticks = np.arange(ymin, ymax + y_step*0.01, y_step)
    if len(x_ticks) > 20:
        x_step = _nice_grid_step(x_range, max_lines=10)
        x_ticks = np.arange(xmin, xmax + x_step*0.01, x_step)
    if len(y_ticks) > 20:
        y_step = _nice_grid_step(y_range, max_lines=10)
        y_ticks = np.arange(ymin, ymax + y_step*0.01, y_step)

    x_label_every = _label_every(len(x_ticks))
    y_label_every = _label_every(len(y_ticks))

    # ── axis headroom: space for arrowhead past the last gridline ──────────
    # Spine extends 0.2 grid units past xmax/ymax; arrow tip is 0.3 past that,
    # so the spine always ends inside the arrowhead with room to spare.
    # The left/bottom margin is exactly zero — no gap before the first gridline.
    # xlim/ylim stop at xmax + stub — spine ends here.
    # Arrow tip extends x_arrow_pad further using clip_on=False so it
    # pokes out past the plot edge and the spine never reaches it.
    x_stub      = x_step * 0.35
    y_stub      = y_step * 0.35
    x_arrow_pad = x_step * 0.25
    y_arrow_pad = y_step * 0.25
    ax.set_xlim(xmin, xmax + x_stub)
    ax.set_ylim(ymin, ymax + y_stub)

    # ── gridlines clipped exactly to [xmin,xmax] × [ymin,ymax] ────────────
    # Using ax.plot instead of axvline/axhline avoids the infinite-line
    # bleed that created the apparent offset at the axes.
    for xt in x_ticks:
        ax.plot([xt, xt], [ymin, ymax], color='#aaaaaa', linewidth=0.6,
                zorder=0, clip_on=True)
    for yt in y_ticks:
        ax.plot([xmin, xmax], [yt, yt], color='#aaaaaa', linewidth=0.6,
                zorder=0, clip_on=True)

    # ── function curves + exit arrows ─────────────────────────────────────
    # Arrow length scaled to the shorter of the two grid steps so it looks
    # consistent regardless of axis range.
    arrow_L = min(x_step, y_step) * 0.45

    for fn in functions:
        f      = fn['expr']
        fprime = fn['deriv']
        color  = fn['color']
        label  = fn.get('label', None)
        x = np.linspace(xmin, xmax, 2000)
        y = f(x)
        mask = (y >= ymin) & (y <= ymax)
        segments = np.split(np.where(mask)[0],
                            np.where(np.diff(np.where(mask)[0]) > 5)[0] + 1)
        for seg in segments:
            if len(seg) > 1:
                ax.plot(x[seg], y[seg], color=color, linewidth=2, label=label)
                label = None

        # right-edge exit arrow (function leaves through xmax)
        yr_val = f(xmax)
        if ymin <= yr_val <= ymax:
            slope = fprime(xmax)
            dx_d, dy_d = 1.0, float(slope)
            mag = np.sqrt(dx_d**2 + dy_d**2)
            if mag > 0.001:
                dx_d /= mag; dy_d /= mag
                ax.annotate('', xy=(xmax + dx_d*arrow_L, yr_val + dy_d*arrow_L),
                                xytext=(xmax, yr_val),
                            arrowprops=dict(arrowstyle='-|>', color=color,
                                            lw=1.5, mutation_scale=14))

        # top/bottom exit arrows (function crosses ymax or ymin)
        x_arr = np.linspace(xmin, xmax, 2000)
        y_arr = f(x_arr)
        for edge_y, direction in [(ymin, -1), (ymax, 1)]:
            vals = y_arr - edge_y
            for idx in np.where(np.diff(np.sign(vals)))[0]:
                xr = np.interp(0, [vals[idx], vals[idx+1]],
                                  [x_arr[idx], x_arr[idx+1]])
                if xr <= xmin + 0.01:
                    continue
                slope = fprime(xr)
                if abs(slope) < 0.001:
                    continue
                dy_d = float(direction)
                dx_d = dy_d / slope
                mag = np.sqrt(dx_d**2 + dy_d**2)
                dx_d /= mag; dy_d /= mag
                ax.annotate('', xy=(xr + dx_d*arrow_L, edge_y + dy_d*arrow_L),
                                xytext=(xr, edge_y),
                            arrowprops=dict(arrowstyle='-|>', color=color,
                                            lw=1.5, mutation_scale=14))

    key_points = _find_key_points(functions, xmin, xmax, ymin, ymax)
    _draw_legend(ax, functions, key_points, xmin, xmax, ymin, ymax)

    # ── tick labels ────────────────────────────────────────────────────────
    x_labeled = [t for i, t in enumerate(x_ticks) if i % x_label_every == 0]
    y_labeled = [t for i, t in enumerate(y_ticks) if i % y_label_every == 0]
    ax.set_xticks(x_labeled)
    ax.set_yticks(y_labeled)
    ax.set_xticklabels([_fmt(t) for t in x_labeled],
                       fontfamily='Times New Roman', fontsize=11)
    ax.set_yticklabels([_fmt(t) for t in y_labeled],
                       fontfamily='Times New Roman', fontsize=11)
    ax.tick_params(which='major', length=4, width=1.0, color='#444444')

    # ── spines: lighter weight, Q1 only ───────────────────────────────────
    ax.spines['left'].set_linewidth(1.8)
    ax.spines['left'].set_color('#222222')
    ax.spines['bottom'].set_linewidth(1.8)
    ax.spines['bottom'].set_color('#222222')
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)

    # ── axis arrowheads ────────────────────────────────────────────────────
    # Tail at xmax/ymax (last gridline), tip beyond xlim/ylim edge.
    # clip_on=False lets the arrowhead render outside the plot area so
    # the spine (which stops at xlim) never reaches the tip.
    tri = dict(arrowstyle='-|>', color='#222222', lw=1.8, mutation_scale=14)
    ax.annotate('', xy=(xmax + x_stub + x_arrow_pad, ymin),
                    xytext=(xmax, ymin),
                arrowprops=tri,
                annotation_clip=False)
    ax.annotate('', xy=(xmin, ymax + y_stub + y_arrow_pad),
                    xytext=(xmin, ymax),
                arrowprops=tri,
                annotation_clip=False)

    ax.set_xlabel(xlabel, fontfamily='Times New Roman', fontsize=13,
                  fontweight='bold', labelpad=6)
    ax.set_ylabel(ylabel, fontfamily='Times New Roman', fontsize=13,
                  fontweight='bold', labelpad=6, rotation=90)
    ax.set_title(title, fontfamily='Times New Roman', fontsize=12, pad=8)


# ─────────────────────────────────────────────────────────────────────────────
# TYPE 3 — NUMBER LINE
# Use for: inequalities, absolute value solutions, domain, range.
#
# intervals : list of dicts
#   'start'      : left endpoint value
#   'end'        : right endpoint value (same as start for rays)
#   'start_open' : True = open circle, False = closed dot
#   'end_open'   : True = open circle, False = closed dot
#   'direction'  : None | 'left' | 'right'  for rays to infinity
#   'color'      : line color (default 'steelblue')
#
# make_number_line_blank() — blank number line with student writing space above
#   label: LaTeX string shown at top  e.g. r'$x > 3$'
# ─────────────────────────────────────────────────────────────────────────────

def _draw_number_line_base(ax, xmin, xmax):
    x_range = xmax - xmin
    margin  = x_range * 0.07
    ticks   = np.arange(xmin, xmax + 0.5)   # one tick per integer, no duplicates
    line_y  = 0.0
    tick_h  = 0.12
    lw_line = 1.8
    lw_tick = 1.2

    right_tip = xmax + margin * 0.95
    left_tip  = xmin - margin * 0.95

    ax.annotate('', xy=(right_tip, line_y), xytext=(left_tip, line_y),
                arrowprops=dict(arrowstyle='->', color='black',
                                lw=lw_line, mutation_scale=14,
                                shrinkA=0, shrinkB=0))
    ax.annotate('', xy=(left_tip, line_y), xytext=(right_tip, line_y),
                arrowprops=dict(arrowstyle='->', color='black',
                                lw=lw_line, mutation_scale=14,
                                shrinkA=0, shrinkB=0))

    for t in ticks:
        ax.plot([t, t], [line_y - tick_h, line_y + tick_h],
                color='black', linewidth=lw_tick, zorder=3)

    for t in ticks:
        tv = int(round(t))
        if tv == 0 or tv % 2 == 0:
            ax.text(t, line_y - tick_h - 0.10, str(tv),
                    ha='center', va='top',
                    fontfamily='Times New Roman', fontsize=11, color='black')

    return margin, right_tip, left_tip


def _nl_dot(ax, x, y, open_dot, color, size=8):
    if open_dot:
        ax.plot(x, y, 'o', markersize=size, markerfacecolor='white',
                markeredgecolor=color, markeredgewidth=2.5, zorder=6,
                clip_on=False)
    else:
        ax.plot(x, y, 'o', markersize=size, markerfacecolor=color,
                markeredgecolor=color, markeredgewidth=2, zorder=6,
                clip_on=False)


def make_number_line(ax, intervals, xmin=-10, xmax=10):
    x_range = xmax - xmin
    line_y  = 0.0
    seg_y   = 0.55
    lw_seg  = 1.8

    ax.set_xlim(xmin - x_range*0.07, xmax + x_range*0.07)
    ax.set_ylim(-0.5, 0.9)
    ax.set_aspect('auto')
    ax.axis('off')
    ax.set_facecolor('white')

    margin, right_tip, left_tip = _draw_number_line_base(ax, xmin, xmax)

    for iv in intervals:
        color      = iv.get('color', 'steelblue')
        start      = iv['start']
        end        = iv['end']
        direction  = iv.get('direction', None)
        start_open = iv.get('start_open', False)
        end_open   = iv.get('end_open', False)

        if direction == 'right':
            _nl_dot(ax, start, line_y, start_open, color)
            ax.plot([start, start], [line_y + 0.06, seg_y],
                    color=color, linewidth=lw_seg, zorder=2,
                    solid_capstyle='butt')
            ax.annotate('', xy=(right_tip * 0.98, seg_y),
                            xytext=(start, seg_y),
                        arrowprops=dict(arrowstyle='->', color=color,
                                        lw=lw_seg, mutation_scale=14,
                                        shrinkA=0, shrinkB=0))

        elif direction == 'left':
            _nl_dot(ax, start, line_y, start_open, color)
            ax.plot([start, start], [line_y + 0.06, seg_y],
                    color=color, linewidth=lw_seg, zorder=2,
                    solid_capstyle='butt')
            ax.annotate('', xy=(left_tip * 0.98, seg_y),
                            xytext=(start, seg_y),
                        arrowprops=dict(arrowstyle='->', color=color,
                                        lw=lw_seg, mutation_scale=14,
                                        shrinkA=0, shrinkB=0))

        else:
            _nl_dot(ax, start, line_y, start_open, color)
            _nl_dot(ax, end,   line_y, end_open,   color)
            ax.plot([start, start], [line_y + 0.06, seg_y],
                    color=color, linewidth=lw_seg, zorder=2,
                    solid_capstyle='butt')
            ax.plot([end, end], [line_y + 0.06, seg_y],
                    color=color, linewidth=lw_seg, zorder=2,
                    solid_capstyle='butt')
            ax.plot([start, end], [seg_y, seg_y],
                    color=color, linewidth=lw_seg,
                    solid_capstyle='butt', zorder=2)


def make_number_line_blank(ax, label=None, xmin=-10, xmax=10):
    x_range = xmax - xmin
    line_y  = 0.0

    ax.set_xlim(xmin - x_range*0.07, xmax + x_range*0.07)
    ax.set_ylim(-0.5, 2.5)
    ax.set_aspect('auto')
    ax.axis('off')
    ax.set_facecolor('white')

    _draw_number_line_base(ax, xmin, xmax)

    if label:
        ax.text(0, 2.2, label, ha='center', va='top',
                fontfamily='Times New Roman', fontsize=12, color='black')


# ─────────────────────────────────────────────────────────────────────────────
# SAVE — 504 x 504 px (3.5 in at 144 dpi)
# Number lines save at 504 x 180 px (3.5 x 1.25 in at 144 dpi)
# ─────────────────────────────────────────────────────────────────────────────

def save_graph(fig, filename):
    path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(path, dpi=144, bbox_inches='tight')
    print(f'Saved: {path}')


# ─────────────────────────────────────────────────────────────────────────────
# PASTE YOUR GRAPH CODE BELOW THIS LINE
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# TYPE 4 — 2x2 GRID
# Four standard coordinate planes in one 504x504 figure.
# Use for: comparing parent functions, transformations, multiple examples.
#
# functions_list : list of 4 function lists, same format as make_standard_graph
# titles         : list of 4 LaTeX title strings e.g. r'$f(x)=x^2$'
# ─────────────────────────────────────────────────────────────────────────────

def _exit_arrows_small(ax, f, fprime, color, xmin, xmax, ymin, ymax):
    x = np.linspace(xmin, xmax, 2000)
    y = f(x)
    exit_points = []
    yl = f(xmin)
    if ymin <= yl <= ymax:
        exit_points.append((xmin, yl, -1, 'side'))
    yr = f(xmax)
    if ymin <= yr <= ymax:
        exit_points.append((xmax, yr, 1, 'side'))
    for edge_y, direction in [(ymin, -1), (ymax, 1)]:
        vals = y - edge_y
        for idx in np.where(np.diff(np.sign(vals)))[0]:
            xr = np.interp(0, [vals[idx], vals[idx+1]], [x[idx], x[idx+1]])
            exit_points.append((xr, edge_y, direction, 'topbot'))
    for (xe, ye, direction, edge) in exit_points:
        slope = fprime(xe)
        if abs(slope) < 0.001:
            continue
        if edge == 'topbot':
            dy_dir = float(direction)
            dx_dir = dy_dir / slope
        else:
            dx_dir = float(direction)
            dy_dir = slope * dx_dir
        mag = np.sqrt(dx_dir**2 + dy_dir**2)
        dx_dir /= mag
        dy_dir /= mag
        L = 0.45
        ax.annotate('', xy=(xe + dx_dir*L, ye + dy_dir*L),
                        xytext=(xe, ye),
                    arrowprops=dict(arrowstyle='-|>', color=color,
                                    lw=1.0, mutation_scale=7))


def make_2x2_grid(functions_list, titles=None):
    if titles is None:
        titles = ['', '', '', '']

    fig, axes = plt.subplots(2, 2, figsize=(3.5, 3.5))
    fig.subplots_adjust(hspace=0.35, wspace=0.25)

    XMIN, XMAX, YMIN, YMAX = -10, 10, -10, 10

    for ax, functions, title in zip(axes.flatten(), functions_list, titles):

        for fn in functions:
            f      = fn['expr']
            fprime = fn['deriv']
            color  = fn['color']
            label  = fn.get('label', None)
            x = np.linspace(XMIN, XMAX, 2000)
            y = f(x)
            mask = (y >= YMIN) & (y <= YMAX)
            segments = np.split(np.where(mask)[0],
                                np.where(np.diff(np.where(mask)[0]) > 5)[0] + 1)
            for seg in segments:
                if len(seg) > 1:
                    ax.plot(x[seg], y[seg], color=color, linewidth=1.2,
                            label=label)
                    label = None
            _exit_arrows_small(ax, f, fprime, color, XMIN, XMAX, YMIN, YMAX)

        ax.set_xlim(XMIN - 0.5, XMAX + 0.5)
        ax.set_ylim(YMIN - 0.5, YMAX + 0.5)

        ax.set_xticks(np.arange(XMIN, XMAX+1, 1), minor=True)
        ax.set_yticks(np.arange(YMIN, YMAX+1, 1), minor=True)
        ax.grid(True, which='minor', color='#aaaaaa', linewidth=0.6)

        ax.set_xticks([-10, -5, 5, 10])
        ax.set_yticks([-10, -5, 5, 10])
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        ax.grid(True, which='major', color='#aaaaaa', linewidth=0.6)
        ax.tick_params(which='major', length=3.5, width=0.9, color='#222222')
        ax.tick_params(which='minor', length=1.0, width=0.4, color='#555555')

        tick_fs = 8.5
        offset  = 1.0
        for val in [-10, -5, 5, 10]:
            lbl = str(val)
            ax.text(val, -offset, lbl, ha='center', va='top',
                    fontsize=tick_fs, fontfamily='Times New Roman',
                    color='black', clip_on=False)
            ax.text(-offset, val, lbl, ha='right', va='center',
                    fontsize=tick_fs, fontfamily='Times New Roman',
                    color='black', clip_on=False)

        ax.spines['left'].set_position('zero')
        ax.spines['bottom'].set_position('zero')
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        for s in ['left', 'bottom']:
            ax.spines[s].set_linewidth(1.4)
            ax.spines[s].set_color('#222222')
        ax.spines['left'].set_bounds(YMIN - 0.5, YMAX + 0.5)
        ax.spines['bottom'].set_bounds(XMIN - 0.5, XMAX + 0.5)

        tri = dict(arrowstyle='-|>', color='#222222', lw=1.4, mutation_scale=8)
        ax.annotate('', xy=(XMAX+0.6, 0), xytext=(XMAX, 0), arrowprops=tri, annotation_clip=False)
        ax.annotate('', xy=(XMIN-0.6, 0), xytext=(XMIN, 0), arrowprops=tri, annotation_clip=False)
        ax.annotate('', xy=(0, YMAX+0.6), xytext=(0, YMAX), arrowprops=tri, annotation_clip=False)
        ax.annotate('', xy=(0, YMIN-0.6), xytext=(0, YMIN), arrowprops=tri, annotation_clip=False)

        ax.text(XMAX + 0.2, 0.9, 'x', fontsize=10, fontweight='bold',
                fontfamily='Times New Roman', ha='center', va='bottom')
        ax.text(0.6, YMAX + 0.2, 'y', fontsize=10, fontweight='bold',
                fontfamily='Times New Roman', ha='left', va='center')

        if title:
            ax.set_title(title, fontsize=11, pad=4)

    return fig

# ─────────────────────────────────────────────────────────────────────────────
# TYPE 9 — 2x1 GRID
# Two coordinate planes side by side, each 504x504px (3.5in).
# Use for: before/after, compare/contrast, function and transformation pairs.
#
# functions_list : list of 2 function lists, same format as make_standard_graph
# titles         : list of 2 LaTeX title strings e.g. r'$f(x)=x^2$'
# ─────────────────────────────────────────────────────────────────────────────

def make_2x1_grid(functions_list, titles=None):
    if titles is None:
        titles = ['', '']

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.5))
    fig.subplots_adjust(wspace=0.3)

    XMIN, XMAX, YMIN, YMAX = -10, 10, -10, 10

    for ax, functions, title in zip(axes, functions_list, titles):

        for fn in functions:
            f      = fn['expr']
            fprime = fn['deriv']
            color  = fn['color']
            label  = fn.get('label', None)
            x = np.linspace(XMIN, XMAX, 2000)
            y = f(x)
            mask = (y >= YMIN) & (y <= YMAX)
            segments = np.split(np.where(mask)[0],
                                np.where(np.diff(np.where(mask)[0]) > 5)[0] + 1)
            for seg in segments:
                if len(seg) > 1:
                    ax.plot(x[seg], y[seg], color=color, linewidth=1.5,
                            label=label)
                    label = None
            _exit_arrows_small(ax, f, fprime, color, XMIN, XMAX, YMIN, YMAX)

        ax.set_xlim(XMIN - 0.5, XMAX + 0.5)
        ax.set_ylim(YMIN - 0.5, YMAX + 0.5)

        ax.set_xticks(np.arange(XMIN, XMAX+1, 1), minor=True)
        ax.set_yticks(np.arange(YMIN, YMAX+1, 1), minor=True)
        ax.grid(True, which='minor', color='#aaaaaa', linewidth=0.6)

        ax.set_xticks([-10, -5, 5, 10])
        ax.set_yticks([-10, -5, 5, 10])
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        ax.grid(True, which='major', color='#aaaaaa', linewidth=0.6)
        ax.tick_params(which='major', length=3.5, width=0.9, color='#222222')
        ax.tick_params(which='minor', length=1.0, width=0.4, color='#555555')

        tick_fs = 8.5
        offset  = 1.0
        for val in [-10, -5, 5, 10]:
            lbl = str(val)
            ax.text(val, -offset, lbl, ha='center', va='top',
                    fontsize=tick_fs, fontfamily='Times New Roman',
                    color='black', clip_on=False)
            ax.text(-offset, val, lbl, ha='right', va='center',
                    fontsize=tick_fs, fontfamily='Times New Roman',
                    color='black', clip_on=False)

        ax.spines['left'].set_position('zero')
        ax.spines['bottom'].set_position('zero')
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        for s in ['left', 'bottom']:
            ax.spines[s].set_linewidth(1.4)
            ax.spines[s].set_color('#222222')
        ax.spines['left'].set_bounds(YMIN - 0.5, YMAX + 0.5)
        ax.spines['bottom'].set_bounds(XMIN - 0.5, XMAX + 0.5)

        tri = dict(arrowstyle='-|>', color='#222222', lw=1.4, mutation_scale=8)
        ax.annotate('', xy=(XMAX+0.6, 0), xytext=(XMAX, 0), arrowprops=tri, annotation_clip=False)
        ax.annotate('', xy=(XMIN-0.6, 0), xytext=(XMIN, 0), arrowprops=tri, annotation_clip=False)
        ax.annotate('', xy=(0, YMAX+0.6), xytext=(0, YMAX), arrowprops=tri, annotation_clip=False)
        ax.annotate('', xy=(0, YMIN-0.6), xytext=(0, YMIN), arrowprops=tri, annotation_clip=False)

        ax.text(XMAX + 0.2, 0.9, 'x', fontsize=10, fontweight='bold',
                fontfamily='Times New Roman', ha='center', va='bottom')
        ax.text(0.6, YMAX + 0.2, 'y', fontsize=10, fontweight='bold',
                fontfamily='Times New Roman', ha='left', va='center')

        if title:
            ax.set_title(title, fontsize=11, pad=4)

    return fig

# ─────────────────────────────────────────────────────────────────────────────
# TYPE 5 — 3x1 GRID
# Three coordinate planes side by side, each ~300px wide.
# Use for: comparing transformations, showing shift/stretch/reflect series.
#
# functions_list : list of 3 function lists, same format as make_standard_graph
# titles         : list of 3 LaTeX title strings e.g. r'$f(x)=x^2$'
# ─────────────────────────────────────────────────────────────────────────────

def make_3x1_grid(functions_list, titles=None):
    if titles is None:
        titles = ['', '', '']

    fig, axes = plt.subplots(1, 3, figsize=(6.25, 2.08))
    fig.subplots_adjust(wspace=0.3)

    XMIN, XMAX, YMIN, YMAX = -10, 10, -10, 10

    for ax, functions, title in zip(axes, functions_list, titles):

        for fn in functions:
            f      = fn['expr']
            fprime = fn['deriv']
            color  = fn['color']
            label  = fn.get('label', None)
            x = np.linspace(XMIN, XMAX, 2000)
            y = f(x)
            mask = (y >= YMIN) & (y <= YMAX)
            segments = np.split(np.where(mask)[0],
                                np.where(np.diff(np.where(mask)[0]) > 5)[0] + 1)
            for seg in segments:
                if len(seg) > 1:
                    ax.plot(x[seg], y[seg], color=color, linewidth=1.2,
                            label=label)
                    label = None
            _exit_arrows_small(ax, f, fprime, color, XMIN, XMAX, YMIN, YMAX)

        ax.set_xlim(XMIN - 0.5, XMAX + 0.5)
        ax.set_ylim(YMIN - 0.5, YMAX + 0.5)

        ax.set_xticks(np.arange(XMIN, XMAX+1, 1), minor=True)
        ax.set_yticks(np.arange(YMIN, YMAX+1, 1), minor=True)
        ax.grid(True, which='minor', color='#aaaaaa', linewidth=0.6)

        ax.set_xticks([-10, -5, 5, 10])
        ax.set_yticks([-10, -5, 5, 10])
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        ax.grid(True, which='major', color='#aaaaaa', linewidth=0.6)
        ax.tick_params(which='major', length=3.5, width=0.9, color='#222222')
        ax.tick_params(which='minor', length=1.0, width=0.4, color='#555555')

        tick_fs = 8.5
        offset  = 1.0
        for val in [-10, -5, 5, 10]:
            lbl = str(val)
            ax.text(val, -offset, lbl, ha='center', va='top',
                    fontsize=tick_fs, fontfamily='Times New Roman',
                    color='black', clip_on=False)
            ax.text(-offset, val, lbl, ha='right', va='center',
                    fontsize=tick_fs, fontfamily='Times New Roman',
                    color='black', clip_on=False)

        ax.spines['left'].set_position('zero')
        ax.spines['bottom'].set_position('zero')
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        for s in ['left', 'bottom']:
            ax.spines[s].set_linewidth(1.4)
            ax.spines[s].set_color('#222222')
        ax.spines['left'].set_bounds(YMIN - 0.5, YMAX + 0.5)
        ax.spines['bottom'].set_bounds(XMIN - 0.5, XMAX + 0.5)

        tri = dict(arrowstyle='-|>', color='#222222', lw=1.4, mutation_scale=8)
        ax.annotate('', xy=(XMAX+0.6, 0), xytext=(XMAX, 0), arrowprops=tri, annotation_clip=False)
        ax.annotate('', xy=(XMIN-0.6, 0), xytext=(XMIN, 0), arrowprops=tri, annotation_clip=False)
        ax.annotate('', xy=(0, YMAX+0.6), xytext=(0, YMAX), arrowprops=tri, annotation_clip=False)
        ax.annotate('', xy=(0, YMIN-0.6), xytext=(0, YMIN), arrowprops=tri, annotation_clip=False)

        ax.text(XMAX + 0.2, 0.9, 'x', fontsize=10, fontweight='bold',
                fontfamily='Times New Roman', ha='center', va='bottom')
        ax.text(0.6, YMAX + 0.2, 'y', fontsize=10, fontweight='bold',
                fontfamily='Times New Roman', ha='left', va='center')

        if title:
            ax.set_title(title, fontsize=11, pad=4)

    return fig

# ─────────────────────────────────────────────────────────────────────────────
# TYPE 6 — 4x1 GRID
# Four coordinate planes side by side, each ~225px wide.
# Use for: comparing four transformations or four parent functions in a row.
#
# functions_list : list of 4 function lists, same format as make_standard_graph
# titles         : list of 4 LaTeX title strings e.g. r'$f(x)=x^2$'
# ─────────────────────────────────────────────────────────────────────────────

def make_4x1_grid(functions_list, titles=None):
    if titles is None:
        titles = ['', '', '', '']

    fig, axes = plt.subplots(1, 4, figsize=(6.25, 1.56))
    fig.subplots_adjust(wspace=0.35)

    XMIN, XMAX, YMIN, YMAX = -10, 10, -10, 10

    for ax, functions, title in zip(axes, functions_list, titles):

        for fn in functions:
            f      = fn['expr']
            fprime = fn['deriv']
            color  = fn['color']
            label  = fn.get('label', None)
            x = np.linspace(XMIN, XMAX, 2000)
            y = f(x)
            mask = (y >= YMIN) & (y <= YMAX)
            segments = np.split(np.where(mask)[0],
                                np.where(np.diff(np.where(mask)[0]) > 5)[0] + 1)
            for seg in segments:
                if len(seg) > 1:
                    ax.plot(x[seg], y[seg], color=color, linewidth=1.5,
                            label=label)
                    label = None
            _exit_arrows_small(ax, f, fprime, color, XMIN, XMAX, YMIN, YMAX)

        ax.set_xlim(XMIN - 0.5, XMAX + 0.5)
        ax.set_ylim(YMIN - 0.5, YMAX + 0.5)

        ax.set_xticks(np.arange(XMIN, XMAX+1, 1), minor=True)
        ax.set_yticks(np.arange(YMIN, YMAX+1, 1), minor=True)
        ax.grid(True, which='minor', color='#aaaaaa', linewidth=0.6)

        ax.set_xticks([-10, -5, 5, 10])
        ax.set_yticks([-10, -5, 5, 10])
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        ax.grid(True, which='major', color='#aaaaaa', linewidth=0.6)
        ax.tick_params(which='major', length=3.5, width=0.9, color='#222222')
        ax.tick_params(which='minor', length=1.0, width=0.4, color='#555555')

        tick_fs = 8.5
        offset  = 1.0
        for val in [-10, -5, 5, 10]:
            lbl = str(val)
            ax.text(val, -offset, lbl, ha='center', va='top',
                    fontsize=tick_fs, fontfamily='Times New Roman',
                    color='black', clip_on=False)
            ax.text(-offset, val, lbl, ha='right', va='center',
                    fontsize=tick_fs, fontfamily='Times New Roman',
                    color='black', clip_on=False)

        ax.spines['left'].set_position('zero')
        ax.spines['bottom'].set_position('zero')
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        for s in ['left', 'bottom']:
            ax.spines[s].set_linewidth(1.4)
            ax.spines[s].set_color('#222222')
        ax.spines['left'].set_bounds(YMIN - 0.5, YMAX + 0.5)
        ax.spines['bottom'].set_bounds(XMIN - 0.5, XMAX + 0.5)

        tri = dict(arrowstyle='-|>', color='#222222', lw=1.4, mutation_scale=8)
        ax.annotate('', xy=(XMAX+0.6, 0), xytext=(XMAX, 0), arrowprops=tri, annotation_clip=False)
        ax.annotate('', xy=(XMIN-0.6, 0), xytext=(XMIN, 0), arrowprops=tri, annotation_clip=False)
        ax.annotate('', xy=(0, YMAX+0.6), xytext=(0, YMAX), arrowprops=tri, annotation_clip=False)
        ax.annotate('', xy=(0, YMIN-0.6), xytext=(0, YMIN), arrowprops=tri, annotation_clip=False)

        ax.text(XMAX + 0.2, 0.9, 'x', fontsize=10, fontweight='bold',
                fontfamily='Times New Roman', ha='center', va='bottom')
        ax.text(0.6, YMAX + 0.2, 'y', fontsize=10, fontweight='bold',
                fontfamily='Times New Roman', ha='left', va='center')

        if title:
            ax.set_title(title, fontsize=11, pad=4)

    return fig

# ─────────────────────────────────────────────────────────────────────────────
# TYPE 7 — RECTANGLE MODEL (AREA MODEL)
# Use for: multiplying polynomials, factoring, generic rectangle.
# Scales automatically to any number of rows and columns.
#
# row_labels  : list of LaTeX strings  e.g. [r'$4x$', r'$-5y$']
# col_labels  : list of LaTeX strings  e.g. [r'$2x$', r'$-3y$']
# cell_values : 2D list — use r'$...$' for LaTeX, '' for blank
#               e.g. [[r'$8x^2$', r'$-12xy$'], [r'$-10xy$', r'$15y^2$']]
# filename    : saved to ./figures
# ─────────────────────────────────────────────────────────────────────────────

def make_rectangle_model(row_labels, col_labels, cell_values,
                         filename='rectangle_model.png'):
    import matplotlib.patches as patches

    n_rows = len(row_labels)
    n_cols = len(col_labels)

    cell_w = 0.75
    cell_h = 0.50
    margin = 0.40

    fig_w = margin + n_cols * cell_w + margin
    fig_h = margin + n_rows * cell_h + margin

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis('off')
    ax.set_facecolor('white')
    fig.patch.set_facecolor('white')

    grid_x = margin
    grid_y = margin * 0.5

    for r in range(n_rows):
        for c in range(n_cols):
            cell_left   = grid_x + c * cell_w
            cell_bottom = grid_y + (n_rows - 1 - r) * cell_h
            rect = patches.Rectangle(
                (cell_left, cell_bottom), cell_w, cell_h,
                linewidth=1.2, edgecolor='black', facecolor='white'
            )
            ax.add_patch(rect)
            val = cell_values[r][c]
            if val:
                ax.text(cell_left + cell_w/2, cell_bottom + cell_h/2, val,
                        ha='center', va='center',
                        fontsize=13, fontfamily='Times New Roman')

    for c, lbl in enumerate(col_labels):
        cx = grid_x + c * cell_w + cell_w/2
        cy = grid_y + n_rows * cell_h + 0.10
        ax.text(cx, cy, lbl, ha='center', va='bottom',
                fontsize=13, fontfamily='Times New Roman')

    for r, lbl in enumerate(row_labels):
        rx = grid_x - 0.10
        ry = grid_y + (n_rows - 1 - r) * cell_h + cell_h/2
        ax.text(rx, ry, lbl, ha='right', va='center',
                fontsize=13, fontfamily='Times New Roman')

    path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(path, dpi=144, bbox_inches='tight')
    print(f'Saved: {path}')

    # ─────────────────────────────────────────────────────────────────────────────
# TYPE 8 — DIAMOND PROBLEM
# Use for: diamond problems, factoring, sum/product puzzles.
# Top = product, bottom = sum, left and right = the two factors.
# Any cell can be '' for blank — student fills it in.
#
# top    : product value  e.g. r'$-42$'  or  r'$xy$'
# left   : left factor    e.g. r'$3$'    or  r'$x$'
# right  : right factor   e.g. r'$-14$'  or  r'$y$'
# bottom : sum value      e.g. r'$-11$'  or  r'$x+y$'
# filename : saved to ./figures
# ─────────────────────────────────────────────────────────────────────────────

def make_diamond(top, left, right, bottom, filename='diamond.png'):
    import matplotlib.pyplot as plt

    size = 2.5
    fig, ax = plt.subplots(figsize=(size, size))
    ax.set_xlim(-1, 1)
    ax.set_ylim(-1, 1)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_facecolor('white')
    fig.patch.set_facecolor('white')

    r = 0.85

    top_pt    = ( 0,  r)
    right_pt  = ( r,  0)
    bottom_pt = ( 0, -r)
    left_pt   = (-r,  0)

    mid_top_right    = ((top_pt[0]+right_pt[0])/2,    (top_pt[1]+right_pt[1])/2)
    mid_right_bottom = ((right_pt[0]+bottom_pt[0])/2, (right_pt[1]+bottom_pt[1])/2)
    mid_bottom_left  = ((bottom_pt[0]+left_pt[0])/2,  (bottom_pt[1]+left_pt[1])/2)
    mid_left_top     = ((left_pt[0]+top_pt[0])/2,     (left_pt[1]+top_pt[1])/2)

    diamond = plt.Polygon(
        [top_pt, right_pt, bottom_pt, left_pt],
        closed=True, linewidth=1.4,
        edgecolor='black', facecolor='white', zorder=2
    )
    ax.add_patch(diamond)

    ax.plot([mid_left_top[0], mid_right_bottom[0]],
            [mid_left_top[1], mid_right_bottom[1]],
            color='black', linewidth=1.0, zorder=3)
    ax.plot([mid_top_right[0], mid_bottom_left[0]],
            [mid_top_right[1], mid_bottom_left[1]],
            color='black', linewidth=1.0, zorder=3)

    pad = 0.38
    positions = {
        'top':    ( 0,    pad),
        'bottom': ( 0,   -pad),
        'left':   (-pad,  0),
        'right':  ( pad,  0),
    }

    for cell, val in [('top', top), ('bottom', bottom),
                      ('left', left), ('right', right)]:
        if val:
            ax.text(*positions[cell], val,
                    ha='center', va='center',
                    fontsize=16, fontfamily='Times New Roman',
                    zorder=4)

    path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(path, dpi=144, bbox_inches='tight')
    print(f'Saved: {path}')

# ─────────────────────────────────────────────────────────────────────────────
# TYPE 10 — PIECEWISE FUNCTION
# Standard -10 to 10 plane. Each piece has its own domain; all pieces draw in steelblue.
# Dots are automatic — closed if endpoint included, open if not.
# Arrows drawn at window edges when piece extends to infinity.
#
# pieces : list of dicts, each with:
#   'expr'          : lambda x: ...    the function expression
#   'deriv'         : lambda x: ...    its derivative
#   'domain'        : (a, b)           interval for this piece
#   'include_left'  : True/False       closed dot on left endpoint
#   'include_right' : True/False       closed dot on right endpoint
#   'color'         : optional; ignored for consistency (all pieces use steelblue)
#   'arrow_left'    : True/False       exit arrow at left end
#   'arrow_right'   : True/False       exit arrow at right end
#
# title: LaTeX supported via r'$...$'
# ─────────────────────────────────────────────────────────────────────────────

def _pw_dot(ax, x, y, open_dot, color, size=7, dot_scale=0.65):
    size = size * dot_scale
    if open_dot:
        ax.plot(x, y, 'o', markersize=size, markerfacecolor='white',
                markeredgecolor=color, markeredgewidth=2, zorder=6,
                clip_on=False)
    else:
        ax.plot(x, y, 'o', markersize=size, markerfacecolor=color,
                markeredgecolor=color, markeredgewidth=2, zorder=6,
                clip_on=False)


def make_piecewise_graph(ax, pieces, title='', dot_scale=0.65):
    XMIN, XMAX, YMIN, YMAX = -10, 10, -10, 10

    for piece in pieces:
        f          = piece['expr']
        fprime     = piece['deriv']
        color      = 'steelblue'
        a, b       = piece['domain']
        inc_left   = piece.get('include_left',  True)
        inc_right  = piece.get('include_right', True)
        arrow_left  = piece.get('arrow_left',  False)
        arrow_right = piece.get('arrow_right', False)

        x_seg = np.linspace(a, b, 1000)
        y_seg = f(x_seg)
        mask  = (y_seg >= YMIN) & (y_seg <= YMAX)
        if mask.any():
            ax.plot(x_seg[mask], y_seg[mask],
                    color=color, linewidth=1.7, zorder=3)

        ya = f(a)
        if not arrow_left and YMIN <= ya <= YMAX:
            _pw_dot(ax, a, ya, open_dot=not inc_left, color=color, dot_scale=dot_scale)

        yb = f(b)
        if not arrow_right and YMIN <= yb <= YMAX:
            _pw_dot(ax, b, yb, open_dot=not inc_right, color=color, dot_scale=dot_scale)

        if arrow_left and YMIN <= ya <= YMAX:
            slope = fprime(a)
            if abs(slope) >= 0.001:
                dx_dir = -1.0
                dy_dir = slope * dx_dir
                mag = np.sqrt(dx_dir**2 + dy_dir**2)
                dx_dir /= mag; dy_dir /= mag
                ax.annotate('', xy=(a + dx_dir*0.45, ya + dy_dir*0.45),
                                xytext=(a, ya),
                            arrowprops=dict(arrowstyle='-|>', color=color,
                                            lw=1.5, mutation_scale=12))

        if arrow_right and YMIN <= yb <= YMAX:
            slope = fprime(b)
            if abs(slope) >= 0.001:
                dx_dir = 1.0
                dy_dir = slope * dx_dir
                mag = np.sqrt(dx_dir**2 + dy_dir**2)
                dx_dir /= mag; dy_dir /= mag
                ax.annotate('', xy=(b + dx_dir*0.45, yb + dy_dir*0.45),
                                xytext=(b, yb),
                            arrowprops=dict(arrowstyle='-|>', color=color,
                                            lw=1.5, mutation_scale=12))

        for edge_y, direction in [(YMIN, -1), (YMAX, 1)]:
            vals = y_seg - edge_y
            for idx in np.where(np.diff(np.sign(vals)))[0]:
                xr = np.interp(0, [vals[idx], vals[idx+1]],
                                  [x_seg[idx], x_seg[idx+1]])
                slope = fprime(xr)
                if abs(slope) < 0.001:
                    continue
                dy_dir = float(direction)
                dx_dir = dy_dir / slope
                mag = np.sqrt(dx_dir**2 + dy_dir**2)
                dx_dir /= mag; dy_dir /= mag
                ax.annotate('', xy=(xr + dx_dir*0.45, edge_y + dy_dir*0.45),
                                xytext=(xr, edge_y),
                            arrowprops=dict(arrowstyle='-|>', color=color,
                                            lw=1.5, mutation_scale=12))

    ax.set_xlim(XMIN - 0.5, XMAX + 0.5)
    ax.set_ylim(YMIN - 0.5, YMAX + 0.5)
    ax.set_xticks(np.arange(XMIN, XMAX+1, 1), minor=True)
    ax.set_yticks(np.arange(YMIN, YMAX+1, 1), minor=True)
    ax.grid(True, which='minor', color='#aaaaaa', linewidth=0.6)
    ax.set_xticks([-10, -5, 5, 10])
    ax.set_yticks([-10, -5, 5, 10])
    ax.set_xticklabels(['-10','-5','5','10'],
                       fontfamily='Times New Roman', fontsize=11)
    ax.set_yticklabels(['-10','-5','5','10'],
                       fontfamily='Times New Roman', fontsize=11)
    ax.grid(True, which='major', color='#aaaaaa', linewidth=0.6)
    ax.tick_params(which='major', length=5, width=1.2, color='#222222')
    ax.tick_params(which='minor', length=2, width=0.8, color='#555555')

    ax.spines['left'].set_position('zero')
    ax.spines['bottom'].set_position('zero')
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    for s in ['left', 'bottom']:
        ax.spines[s].set_linewidth(1.8)
        ax.spines[s].set_color('#222222')
    ax.spines['left'].set_bounds(YMIN - 0.5, YMAX + 0.5)
    ax.spines['bottom'].set_bounds(XMIN - 0.5, XMAX + 0.5)

    tri = dict(arrowstyle='-|>', color='#222222', lw=1.8, mutation_scale=14)
    ax.annotate('', xy=(XMAX+0.6, 0), xytext=(XMAX, 0), arrowprops=tri, annotation_clip=False)
    ax.annotate('', xy=(XMIN-0.6, 0), xytext=(XMIN, 0), arrowprops=tri, annotation_clip=False)
    ax.annotate('', xy=(0, YMAX+0.6), xytext=(0, YMAX), arrowprops=tri, annotation_clip=False)
    ax.annotate('', xy=(0, YMIN-0.6), xytext=(0, YMIN), arrowprops=tri, annotation_clip=False)

    ax.text(XMAX+0.35, 0.4, 'x', fontsize=14, fontweight='bold',
            fontfamily='Times New Roman', ha='center', va='bottom')
    ax.text(0.35, YMAX+0.35, 'y', fontsize=14, fontweight='bold',
            fontfamily='Times New Roman', ha='left', va='center')
    ax.set_title(title, fontfamily='Times New Roman', fontsize=12, pad=8)

    # ─────────────────────────────────────────────────────────────────────────────
# TYPE 11 — UNIT CIRCLE
# All variants save at exactly 2.5x2.5in (360x360px at 144dpi).
#
# make_unit_circle_blank()
#   Blank — circle and axes only. Student draws/writes everything.
#
# make_unit_circle_angles(ax_angle_deg=None, show_coord=True, filename=...)
#   ax_angle_deg : int — highlights that angle in blue  e.g. 120
#                  None — semi-blank, just 16 angle lines, nothing highlighted
#   show_coord   : True = coordinate label outside circle, False = no label
#
# Valid angles: 0, 30, 45, 60, 90, 120, 135, 150,
#               180, 210, 225, 240, 270, 300, 315, 330
# ─────────────────────────────────────────────────────────────────────────────

ANGLE_DATA = {
    0:   ( 1,            0           ),
    30:  ( np.sqrt(3)/2, 0.5         ),
    45:  ( np.sqrt(2)/2, np.sqrt(2)/2),
    60:  ( 0.5,          np.sqrt(3)/2),
    90:  ( 0,            1           ),
    120: (-0.5,          np.sqrt(3)/2),
    135: (-np.sqrt(2)/2, np.sqrt(2)/2),
    150: (-np.sqrt(3)/2, 0.5         ),
    180: (-1,            0           ),
    210: (-np.sqrt(3)/2,-0.5         ),
    225: (-np.sqrt(2)/2,-np.sqrt(2)/2),
    240: (-0.5,         -np.sqrt(3)/2),
    270: ( 0,           -1           ),
    300: ( 0.5,         -np.sqrt(3)/2),
    315: ( np.sqrt(2)/2,-np.sqrt(2)/2),
    330: ( np.sqrt(3)/2,-0.5         ),
}

COORD_LABELS = {
    0:   r'$(1, 0)$',
    30:  r'$\left(\frac{\sqrt{3}}{2}, \frac{1}{2}\right)$',
    45:  r'$\left(\frac{\sqrt{2}}{2}, \frac{\sqrt{2}}{2}\right)$',
    60:  r'$\left(\frac{1}{2}, \frac{\sqrt{3}}{2}\right)$',
    90:  r'$(0, 1)$',
    120: r'$\left(-\frac{1}{2}, \frac{\sqrt{3}}{2}\right)$',
    135: r'$\left(-\frac{\sqrt{2}}{2}, \frac{\sqrt{2}}{2}\right)$',
    150: r'$\left(-\frac{\sqrt{3}}{2}, \frac{1}{2}\right)$',
    180: r'$(-1, 0)$',
    210: r'$\left(-\frac{\sqrt{3}}{2}, -\frac{1}{2}\right)$',
    225: r'$\left(-\frac{\sqrt{2}}{2}, -\frac{\sqrt{2}}{2}\right)$',
    240: r'$\left(-\frac{1}{2}, -\frac{\sqrt{3}}{2}\right)$',
    270: r'$(0, -1)$',
    300: r'$\left(\frac{1}{2}, -\frac{\sqrt{3}}{2}\right)$',
    315: r'$\left(\frac{\sqrt{2}}{2}, -\frac{\sqrt{2}}{2}\right)$',
    330: r'$\left(\frac{\sqrt{3}}{2}, -\frac{1}{2}\right)$',
}


def _draw_unit_circle_base(ax, show_angle_lines=False):
    theta = np.linspace(0, 2*np.pi, 1000)
    ax.plot(np.cos(theta), np.sin(theta),
            color='black', linewidth=2.0, zorder=3)

    lw_ax  = 0.6
    col_ax = '#222222'
    ax.plot([-1.3, 1.3], [0, 0], color=col_ax, linewidth=lw_ax, zorder=1)
    ax.plot([0, 0], [-1.3, 1.3], color=col_ax, linewidth=lw_ax, zorder=1)

    tri = dict(arrowstyle='-|>', color=col_ax, lw=lw_ax, mutation_scale=10)
    ax.annotate('', xy=( 1.38, 0),  xytext=( 1.22, 0),  arrowprops=tri)
    ax.annotate('', xy=(-1.38, 0),  xytext=(-1.22, 0),  arrowprops=tri)
    ax.annotate('', xy=( 0,  1.38), xytext=( 0,  1.22), arrowprops=tri)
    ax.annotate('', xy=( 0, -1.38), xytext=( 0, -1.22), arrowprops=tri)

    ax.text( 1.44, 0,  'x', ha='left',   va='center', fontsize=8,
             fontfamily='Times New Roman', color=col_ax)
    ax.text( 0,  1.44, 'y', ha='center', va='bottom', fontsize=8,
             fontfamily='Times New Roman', color=col_ax)

    if show_angle_lines:
        for deg in ANGLE_DATA:
            rad = np.radians(deg)
            ax.plot([0, np.cos(rad)], [0, np.sin(rad)],
                    color='#aaaaaa', linewidth=0.6, zorder=2)

    ax.set_xlim(-1.6, 1.6)
    ax.set_ylim(-1.6, 1.6)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_facecolor('white')


def _uc_save(fig, filename):
    path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(path, dpi=144)
    print(f'Saved: {path}')


def make_unit_circle_blank(filename='unit_circle_blank.png'):
    fig, ax = plt.subplots(figsize=(2.5, 2.5))
    fig.patch.set_facecolor('white')
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    _draw_unit_circle_base(ax, show_angle_lines=False)
    _uc_save(fig, filename)


def make_unit_circle_angles(ax_angle_deg=None, show_coord=True,
                             filename='unit_circle_angles.png'):
    fig, ax = plt.subplots(figsize=(2.5, 2.5))
    fig.patch.set_facecolor('white')
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    _draw_unit_circle_base(ax, show_angle_lines=True)

    if ax_angle_deg is not None:
        blue = '#1a4f8a'
        rad  = np.radians(ax_angle_deg)
        px   = np.cos(rad)
        py   = np.sin(rad)

        ax.plot([0, px], [0, py], color=blue, linewidth=1.8, zorder=4)
        ax.plot(px, py, 'o', markersize=5, color=blue, zorder=5)

        if show_coord and ax_angle_deg in COORD_LABELS:
            lx = px * 1.12
            ly = py * 1.12
            ha = 'center'
            if px > 0.15:  ha = 'left'
            if px < -0.15: ha = 'right'
            va = 'center'
            if py > 0.15:  va = 'bottom'
            if py < -0.15: va = 'top'
            ax.text(lx, ly, COORD_LABELS[ax_angle_deg],
                    ha=ha, va=va, fontsize=12, color=blue,
                    fontfamily='Times New Roman', zorder=6)

    _uc_save(fig, filename)

    # ─────────────────────────────────────────────────────────────────────────────
# TYPE 12 — 2D INEQUALITY / SYSTEM OF INEQUALITIES
# Standard plane extended to ±11 so exit arrows clear the grid.
# Single inequality or system of 2 (overlap shown in mediumpurple).
#
# inequalities : list of dicts, each with:
#   'expr'      : lambda x: ...    boundary line function
#   'deriv'     : lambda x: ...    its derivative
#   'color'     : 'steelblue'
#   'shade'     : 'above' or 'below'
#   'inclusive' : True = solid line, False = dashed line
#
# title: LaTeX supported via r'$...$'
# ─────────────────────────────────────────────────────────────────────────────

def make_inequality_graph(ax, inequalities, title=''):
    XMIN, XMAX, YMIN, YMAX = -11, 11, -11, 11
    x = np.linspace(XMIN, XMAX, 2000)

    shade_regions = []

    for ineq in inequalities:
        f         = ineq['expr']
        fprime    = ineq['deriv']
        color     = ineq['color']
        shade     = ineq['shade']
        inclusive = ineq.get('inclusive', True)

        y = f(x)
        y_clipped = np.clip(y, YMIN, YMAX)
        shade_regions.append({'y': y_clipped, 'shade': shade, 'color': color})

        linestyle = '-' if inclusive else '--'
        mask = (y >= YMIN) & (y <= YMAX)
        segments = np.split(np.where(mask)[0],
                            np.where(np.diff(np.where(mask)[0]) > 5)[0] + 1)
        for seg in segments:
            if len(seg) > 1:
                ax.plot(x[seg], y[seg], color=color, linewidth=2,
                        linestyle=linestyle, zorder=4)

        exit_points = []
        yl = f(XMIN)
        if YMIN <= yl <= YMAX:
            exit_points.append((float(XMIN), float(yl), 'left'))
        yr = f(XMAX)
        if YMIN <= yr <= YMAX:
            exit_points.append((float(XMAX), float(yr), 'right'))
        for edge_y, edge_dir in [(YMIN, 'bottom'), (YMAX, 'top')]:
            vals = y - edge_y
            for idx in np.where(np.diff(np.sign(vals)))[0]:
                xr = float(np.interp(0, [vals[idx], vals[idx+1]],
                                        [x[idx], x[idx+1]]))
                exit_points.append((xr, float(edge_y), edge_dir))

        for (xe, ye, edge) in exit_points:
            slope = float(fprime(np.array([xe]))[0])
            if edge == 'right':
                dx_dir =  1.0
                dy_dir =  float(slope)
            elif edge == 'left':
                dx_dir = -1.0
                dy_dir = -float(slope)
            elif edge == 'top':
                dy_dir =  1.0
                dx_dir =  float(1.0 / slope) if abs(slope) > 0.001 else 0.0
            else:
                dy_dir = -1.0
                dx_dir = -float(1.0 / slope) if abs(slope) > 0.001 else 0.0
            mag = float(np.sqrt(dx_dir**2 + dy_dir**2))
            if mag < 0.001:
                continue
            dx_dir /= mag
            dy_dir /= mag
            L = 0.55
            ax.annotate('',
                        xy=(xe + dx_dir*L, ye + dy_dir*L),
                        xytext=(xe - dx_dir*0.1, ye - dy_dir*0.1),
                        arrowprops=dict(arrowstyle='-|>', color=color,
                                        lw=1.5, mutation_scale=12),
                        annotation_clip=False)

    for sr in shade_regions:
        if sr['shade'] == 'above':
            ax.fill_between(x, sr['y'], YMAX,
                            where=(sr['y'] <= YMAX),
                            color=sr['color'], alpha=0.15, zorder=2)
        elif sr['shade'] == 'below':
            ax.fill_between(x, YMIN, sr['y'],
                            where=(sr['y'] >= YMIN),
                            color=sr['color'], alpha=0.15, zorder=2)

    if len(shade_regions) == 2:
        sr0, sr1 = shade_regions[0], shade_regions[1]
        y0_top = np.full(len(x), float(YMAX)) if sr0['shade'] == 'above' else sr0['y']
        y0_bot = sr0['y'] if sr0['shade'] == 'above' else np.full(len(x), float(YMIN))
        y1_top = np.full(len(x), float(YMAX)) if sr1['shade'] == 'above' else sr1['y']
        y1_bot = sr1['y'] if sr1['shade'] == 'above' else np.full(len(x), float(YMIN))
        overlap_top = np.minimum(y0_top, y1_top)
        overlap_bot = np.maximum(y0_bot, y1_bot)
        has_overlap = overlap_top > overlap_bot
        if has_overlap.any():
            ax.fill_between(x, overlap_bot, overlap_top,
                            where=has_overlap,
                            color='mediumpurple', alpha=0.45, zorder=3)

    ax.set_xlim(-10.5, 10.5)
    ax.set_ylim(-10.5, 10.5)
    ax.set_xticks(np.arange(-10, 11, 1), minor=True)
    ax.set_yticks(np.arange(-10, 11, 1), minor=True)
    ax.grid(True, which='minor', color='#aaaaaa', linewidth=0.6)
    ax.set_xticks([-10, -5, 5, 10])
    ax.set_yticks([-10, -5, 5, 10])
    ax.set_xticklabels(['-10','-5','5','10'],
                       fontfamily='Times New Roman', fontsize=11)
    ax.set_yticklabels(['-10','-5','5','10'],
                       fontfamily='Times New Roman', fontsize=11)
    ax.grid(True, which='major', color='#aaaaaa', linewidth=0.6)
    ax.tick_params(which='major', length=5, width=1.2, color='#222222')
    ax.tick_params(which='minor', length=2, width=0.8, color='#555555')

    ax.spines['left'].set_position('zero')
    ax.spines['bottom'].set_position('zero')
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    for s in ['left', 'bottom']:
        ax.spines[s].set_linewidth(1.8)
        ax.spines[s].set_color('#222222')
    ax.spines['left'].set_bounds(-10.5, 10.5)
    ax.spines['bottom'].set_bounds(-10.5, 10.5)

    tri = dict(arrowstyle='-|>', color='#222222', lw=1.8, mutation_scale=14)
    ax.annotate('', xy=( 11.6,  0), xytext=( 10,  0), arrowprops=tri, annotation_clip=False)
    ax.annotate('', xy=(-11.6,  0), xytext=(-10,  0), arrowprops=tri, annotation_clip=False)
    ax.annotate('', xy=( 0,  11.6), xytext=( 0,  10), arrowprops=tri, annotation_clip=False)
    ax.annotate('', xy=( 0, -11.6), xytext=( 0, -10), arrowprops=tri, annotation_clip=False)

    ax.text(11.8, 0.4, 'x', fontsize=14, fontweight='bold',
            fontfamily='Times New Roman', ha='center', va='bottom')
    ax.text(0.35, 11.8, 'y', fontsize=14, fontweight='bold',
            fontfamily='Times New Roman', ha='left', va='center')
    ax.set_title(title, fontfamily='Times New Roman', fontsize=12, pad=22)

    # ─────────────────────────────────────────────────────────────────────────────
# TYPE 13 — TRIG GRAPH (sine and cosine)
# Landscape figure 5x2.5in. Shows 2 full periods.
# x-axis labeled in π fractions. y-axis scales to amplitude.
#
# functions : list of dicts, each with:
#   'type'  : 'sin' or 'cos'
#   'a'     : amplitude          (default 1)
#   'b'     : frequency          (default 1)
#   'c'     : phase shift        (default 0)  f(x) = a·sin(b(x-c)) + d
#   'd'     : vertical shift     (default 0)
#   'color' : 'steelblue'
#
# title: LaTeX supported via r'$...$'
# ─────────────────────────────────────────────────────────────────────────────

def make_trig_graph(ax, functions, title=''):
    max_amp = max(abs(fn.get('a', 1)) + abs(fn.get('d', 0))
                  for fn in functions)
    y_max = max(np.ceil(max_amp * 1.3), 2)

    min_b = min(abs(fn.get('b', 1)) for fn in functions)
    period = 2 * np.pi / min_b
    x_max = period
    x = np.linspace(-x_max, x_max, 3000)

    for fn in functions:
        ftype = fn.get('type', 'sin')
        a     = fn.get('a', 1)
        b     = fn.get('b', 1)
        c     = fn.get('c', 0)
        d     = fn.get('d', 0)
        color = fn.get('color', 'steelblue')

        if ftype == 'sin':
            y = a * np.sin(b * (x - c)) + d
        else:
            y = a * np.cos(b * (x - c)) + d

        ax.plot(x, y, color=color, linewidth=2, zorder=3)

    ax.set_ylim(-y_max - 0.3, y_max + 0.3)
    ax.set_xlim(-x_max - 0.2, x_max + 0.2)

    step = np.pi / (4 * min_b)
    x_ticks = np.arange(-x_max, x_max + step*0.01, step)

    def pi_label(v):
        from fractions import Fraction
        v_pi = round(v / np.pi * 8) / 8
        if v_pi == 0:
            return '0'
        frac = Fraction(v_pi).limit_denominator(8)
        num, den = frac.numerator, frac.denominator
        if den == 1:
            if num ==  1: return r'$\pi$'
            if num == -1: return r'$-\pi$'
            return rf'${num}\pi$'
        if num ==  1: return rf'$\frac{{\pi}}{{{den}}}$'
        if num == -1: return rf'$-\frac{{\pi}}{{{den}}}$'
        if num <   0: return rf'$-\frac{{{abs(num)}\pi}}{{{den}}}$'
        return rf'$\frac{{{num}\pi}}{{{den}}}$'

    label_every = 2
    ax.set_xticks(x_ticks)
    x_labels = [pi_label(t) if i % label_every == 0 else ''
                for i, t in enumerate(x_ticks)]
    ax.set_xticklabels(x_labels, fontfamily='Times New Roman', fontsize=10)

    y_ticks = np.arange(-int(y_max), int(y_max)+1, 1)
    ax.set_yticks(y_ticks)
    y_labels = [str(int(t)) if t != 0 else '' for t in y_ticks]
    ax.set_yticklabels(y_labels, fontfamily='Times New Roman', fontsize=10)

    ax.grid(True, color='#aaaaaa', linewidth=0.6, zorder=0)
    ax.tick_params(which='major', length=4, width=1.0, color='#222222')

    ax.spines['left'].set_position('zero')
    ax.spines['bottom'].set_position('zero')
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    for s in ['left', 'bottom']:
        ax.spines[s].set_linewidth(1.8)
        ax.spines[s].set_color('#222222')
    ax.spines['left'].set_bounds(-y_max, y_max)
    ax.spines['bottom'].set_bounds(-x_max, x_max)

    tri = dict(arrowstyle='-|>', color='#222222', lw=2.0, mutation_scale=14)
    ax.annotate('', xy=( x_max+0.3, 0), xytext=( x_max, 0), arrowprops=tri, annotation_clip=False)
    ax.annotate('', xy=(-x_max-0.3, 0), xytext=(-x_max, 0), arrowprops=tri, annotation_clip=False)
    ax.annotate('', xy=(0,  y_max+0.4), xytext=(0,  y_max), arrowprops=tri, annotation_clip=False)
    ax.annotate('', xy=(0, -y_max-0.4), xytext=(0, -y_max), arrowprops=tri, annotation_clip=False)

    ax.text(x_max+0.35, 0.15, 'x', fontsize=13, fontweight='bold',
            fontfamily='Times New Roman', ha='left', va='bottom')
    ax.text(0.15, y_max+0.3, 'y', fontsize=13, fontweight='bold',
            fontfamily='Times New Roman', ha='left', va='center')

    ax.set_title(title, fontfamily='Times New Roman', fontsize=12, pad=8)

    # ─────────────────────────────────────────────────────────────────────────────
# TYPE 14 — BAR CHART
# Use for: categorical comparisons, survey results, grouped data.
# Landscape 4x3in. Horizontal grid lines only. Times New Roman throughout.
#
# categories : list of strings        e.g. ['Mon', 'Tue', 'Wed']
# values     : list of numbers        e.g. [4, 7, 3]
# colors     : single color or list   (default 'steelblue')
# ylabel     : y-axis label
# xlabel     : x-axis label
# title      : LaTeX supported via r'$...$'
#
# TYPE 15 — HISTOGRAM
# Use for: frequency distributions, data spread, statistics units.
#
# data   : list or array of raw values  e.g. [12, 15, 14, 18, ...]
# bins   : number of bins or list of bin edges (default 10)
# color  : bar color (default 'steelblue')
# ylabel : y-axis label
# xlabel : x-axis label
# title  : LaTeX supported via r'$...$'
# ─────────────────────────────────────────────────────────────────────────────

def make_bar_chart(ax, categories, values, title='',
                   colors=None, ylabel='Frequency', xlabel=''):
    if colors is None:
        colors = 'steelblue'

    n = len(categories)
    x = np.arange(n)

    ax.bar(x, values, color=colors, width=0.6,
           edgecolor='white', linewidth=0.8, zorder=3)

    ax.yaxis.grid(True, color='#aaaaaa', linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    y_max = max(values) * 1.15
    ax.set_ylim(0, y_max)

    ax.set_xticks(x)
    ax.set_xticklabels(categories,
                       fontfamily='Times New Roman', fontsize=11)
    ax.set_xlim(-0.5, n - 0.5)

    ax.yaxis.set_tick_params(labelsize=11)
    for label in ax.get_yticklabels():
        label.set_fontfamily('Times New Roman')

    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['left'].set_linewidth(1.5)
    ax.spines['bottom'].set_linewidth(1.5)
    ax.spines['left'].set_color('#222222')
    ax.spines['bottom'].set_color('#222222')

    ax.set_xlabel(xlabel, fontfamily='Times New Roman',
                  fontsize=12, fontweight='bold', labelpad=6)
    ax.set_ylabel(ylabel, fontfamily='Times New Roman',
                  fontsize=12, fontweight='bold', labelpad=6)
    ax.set_title(title, fontfamily='Times New Roman', fontsize=12, pad=8)


def make_histogram(ax, data, bins=10, title='',
                   color='steelblue', ylabel='Frequency', xlabel='Value'):
    counts, edges, patches = ax.hist(data, bins=bins, color=color,
                                     edgecolor='white', linewidth=0.8,
                                     zorder=3)

    ax.yaxis.grid(True, color='#aaaaaa', linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    y_max = max(counts) * 1.15
    ax.set_ylim(0, y_max)

    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['left'].set_linewidth(1.5)
    ax.spines['bottom'].set_linewidth(1.5)
    ax.spines['left'].set_color('#222222')
    ax.spines['bottom'].set_color('#222222')

    ax.xaxis.set_tick_params(labelsize=11)
    ax.yaxis.set_tick_params(labelsize=11)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontfamily('Times New Roman')

    ax.set_xlabel(xlabel, fontfamily='Times New Roman',
                  fontsize=12, fontweight='bold', labelpad=6)
    ax.set_ylabel(ylabel, fontfamily='Times New Roman',
                  fontsize=12, fontweight='bold', labelpad=6)
    ax.set_title(title, fontfamily='Times New Roman', fontsize=12, pad=8)

    # ─────────────────────────────────────────────────────────────────────────────
# TYPE 16 — SCATTER PLOT
# Use for: data analysis, line of best fit, residuals, sequences/series.
# Custom axis ranges. Optional linear line of best fit with arrows.
# One dataset at a time.
#
# x_data, y_data   : lists or arrays of data points
# xmin/xmax        : x axis range
# ymin/ymax        : y axis range
# color            : point color (default 'steelblue')
# point_size       : dot size (default 25)
# line_of_best_fit : True = draw linear regression line with arrows
# xlabel/ylabel    : axis labels
# title            : LaTeX supported via r'$...$'
# ─────────────────────────────────────────────────────────────────────────────

def make_scatter_plot(ax, x_data, y_data,
                      xmin, xmax, ymin, ymax,
                      color='steelblue', point_size=25, point_scale=0.65,
                      line_of_best_fit=False,
                      xlabel='x', ylabel='y', title=''):

    x_data = np.array(x_data, dtype=float)
    y_data = np.array(y_data, dtype=float)

    ax.scatter(x_data, y_data, color=color, s=point_size * point_scale,
               zorder=4, clip_on=True)

    if line_of_best_fit:
        m, b = np.polyfit(x_data, y_data, 1)
        x_range = xmax - xmin
        x_ext = np.linspace(xmin, xmax, 1000)
        y_ext = m * x_ext + b
        mask = (y_ext >= ymin) & (y_ext <= ymax)

        if mask.any():
            ax.plot(x_ext[mask], y_ext[mask],
                    color='firebrick', linewidth=2, zorder=3)

            y_left = m * xmin + b
            if ymin <= y_left <= ymax:
                dx_dir = -1.0
                dy_dir = -float(m)
                mag = np.sqrt(dx_dir**2 + dy_dir**2)
                dx_dir /= mag; dy_dir /= mag
                L = x_range * 0.04
                ax.annotate('',
                            xy=(xmin + dx_dir*L, y_left + dy_dir*L),
                            xytext=(xmin - dx_dir*0.01, y_left - dy_dir*0.01),
                            arrowprops=dict(arrowstyle='-|>', color='firebrick',
                                            lw=1.5, mutation_scale=12),
                            annotation_clip=False)

            y_right = m * xmax + b
            if ymin <= y_right <= ymax:
                dx_dir = 1.0
                dy_dir = float(m)
                mag = np.sqrt(dx_dir**2 + dy_dir**2)
                dx_dir /= mag; dy_dir /= mag
                L = x_range * 0.04
                ax.annotate('',
                            xy=(xmax + dx_dir*L, y_right + dy_dir*L),
                            xytext=(xmax - dx_dir*0.01, y_right - dy_dir*0.01),
                            arrowprops=dict(arrowstyle='-|>', color='firebrick',
                                            lw=1.5, mutation_scale=12),
                            annotation_clip=False)

            for edge_y, direction in [(ymin, -1), (ymax, 1)]:
                vals = y_ext - edge_y
                for idx in np.where(np.diff(np.sign(vals)))[0]:
                    xr = float(np.interp(0, [vals[idx], vals[idx+1]],
                                            [x_ext[idx], x_ext[idx+1]]))
                    dy_dir = float(direction)
                    dx_dir = float(dy_dir / m) if abs(m) > 0.001 else 0.0
                    mag = np.sqrt(dx_dir**2 + dy_dir**2)
                    if mag < 0.001:
                        continue
                    dx_dir /= mag; dy_dir /= mag
                    L = x_range * 0.04
                    ax.annotate('',
                                xy=(xr + dx_dir*L, edge_y + dy_dir*L),
                                xytext=(xr - dx_dir*0.01, edge_y - dy_dir*0.01),
                                arrowprops=dict(arrowstyle='-|>', color='firebrick',
                                                lw=1.5, mutation_scale=12),
                                annotation_clip=False)

    x_range = xmax - xmin
    y_range = ymax - ymin
    mx = x_range * 0.06
    my = y_range * 0.06

    # Keep the first gridline flush with the left/bottom axes.
    # Reserve headroom only past the final gridline for arrowheads.
    ax.set_xlim(xmin, xmax + mx)
    ax.set_ylim(ymin, ymax + my)

    x_step = _nice_grid_step(x_range)
    y_step = _nice_grid_step(y_range)
    x_ticks = np.arange(xmin, xmax + x_step*0.01, x_step)
    y_ticks = np.arange(ymin, ymax + y_step*0.01, y_step)

    for xt in x_ticks:
        ax.plot([xt, xt], [ymin, ymax], color='#aaaaaa', linewidth=0.6,
                zorder=0, clip_on=True)
    for yt in y_ticks:
        ax.plot([xmin, xmax], [yt, yt], color='#aaaaaa', linewidth=0.6,
                zorder=0, clip_on=True)

    x_label_every = _label_every(len(x_ticks))
    y_label_every = _label_every(len(y_ticks))
    x_labeled = [t for i, t in enumerate(x_ticks) if i % x_label_every == 0]
    y_labeled = [t for i, t in enumerate(y_ticks) if i % y_label_every == 0]

    ax.set_xticks(x_labeled)
    ax.set_yticks(y_labeled)
    ax.set_xticklabels([_fmt(t) for t in x_labeled],
                       fontfamily='Times New Roman', fontsize=11)
    ax.set_yticklabels([_fmt(t) for t in y_labeled],
                       fontfamily='Times New Roman', fontsize=11)
    ax.tick_params(which='major', length=5, width=1.2, color='#222222')

    for s in ['left', 'bottom']:
        ax.spines[s].set_linewidth(1.8)
        ax.spines[s].set_color('#222222')
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['left'].set_bounds(ymin, ymax)
    ax.spines['bottom'].set_bounds(xmin, xmax)

    tri = dict(arrowstyle='-|>', color='#222222', lw=1.8, mutation_scale=14)
    ax.annotate('', xy=(xmax + mx, ymin), xytext=(xmax, ymin),
                arrowprops=tri, annotation_clip=False)
    ax.annotate('', xy=(xmin, ymax + my), xytext=(xmin, ymax),
                arrowprops=tri, annotation_clip=False)

    ax.set_xlabel(xlabel, fontfamily='Times New Roman', fontsize=13,
                  fontweight='bold', labelpad=6)
    ax.set_ylabel(ylabel, fontfamily='Times New Roman', fontsize=13,
                  fontweight='bold', labelpad=6, rotation=90)
    ax.set_title(title, fontfamily='Times New Roman', fontsize=12, pad=8)

    # ─────────────────────────────────────────────────────────────────────────────
# TYPE 17 — HUNDRED GRID (10x10)
# Use for: shading percents, decimals, fractions visually.
# 2.5x2.5in (360x360px at 144dpi).
#
# shaded_cells : int 0-100, fills left to right top to bottom
# shaded_color : color for shaded cells (default 'steelblue')
# filename     : saved to ./figures
# ─────────────────────────────────────────────────────────────────────────────

def make_hundred_grid(shaded_cells=0, shaded_color='steelblue',
                      filename='hundred_grid.png'):
    import matplotlib.patches as patches

    fig, ax = plt.subplots(figsize=(2.5, 2.5))
    fig.patch.set_facecolor('white')
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.set_aspect('equal')
    ax.axis('off')

    for row in range(10):
        for col in range(10):
            cell_num = row * 10 + col
            filled = cell_num < shaded_cells
            rect = patches.Rectangle(
                (col, 9 - row), 1, 1,
                linewidth=0.8,
                edgecolor='#555555',
                facecolor=shaded_color if filled else 'white'
            )
            ax.add_patch(rect)

    path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(path, dpi=144, bbox_inches='tight')
    print(f'Saved: {path}')

    # ─────────────────────────────────────────────────────────────────────────────
# TYPE 18 — FRACTION BAR / TAPE DIAGRAM
# Use for: fractions, ratios, part-part-whole relationships.
# Horizontal bar divided into n equal parts, some shaded left to right.
#
# n_parts      : total number of parts       e.g. 4 for fourths
# n_shaded     : parts shaded from left      (default 0 = blank)
# shaded_color : color for shaded parts      (default 'steelblue')
# label_parts  : True = label each part with fraction e.g. 1/4
# filename     : saved to ./figures
# ─────────────────────────────────────────────────────────────────────────────

def make_fraction_bar(n_parts, n_shaded=0, shaded_color='steelblue',
                      label_parts=True, filename='fraction_bar.png'):
    import matplotlib.patches as patches

    bar_w  = 4.0
    bar_h  = 0.75
    margin = 0.3

    fig_w = bar_w + margin * 2
    fig_h = bar_h + margin * 2

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor('white')
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis('off')
    ax.set_facecolor('white')

    part_w = bar_w / n_parts

    for i in range(n_parts):
        x_left = margin + i * part_w
        filled = i < n_shaded

        rect = patches.Rectangle(
            (x_left, margin), part_w, bar_h,
            linewidth=1.2,
            edgecolor='black',
            facecolor=shaded_color if filled else 'white'
        )
        ax.add_patch(rect)

        if label_parts:
            ax.text(x_left + part_w/2, margin + bar_h/2,
                    rf'$\frac{{1}}{{{n_parts}}}$',
                    ha='center', va='center',
                    fontsize=11, fontfamily='Times New Roman',
                    color='white' if filled else 'black')

    path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(path, dpi=144, bbox_inches='tight')
    print(f'Saved: {path}')

    # ─────────────────────────────────────────────────────────────────────────────
# TYPE 19 — ALGEBRA TILES
# Portrait orientation. Positive = filled color. Negative = red fill.
# White italic LaTeX label inside each tile. Auto-wraps to rows.
#
# expression : dict — any combination of:
#   'x2'      : positive x²  (blue square)
#   'neg_x2'  : negative x²  (red square)
#   'y2'      : positive y²  (blue square)
#   'neg_y2'  : negative y²  (red square)
#   'xy'      : positive xy  (green square)
#   'neg_xy'  : negative xy  (red square)
#   'x'       : positive x   (blue tall narrow rectangle)
#   'neg_x'   : negative x   (red tall narrow rectangle)
#   'y'       : positive y   (purple tall narrow rectangle)
#   'neg_y'   : negative y   (red tall narrow rectangle)
#   'one'     : positive 1   (dark blue small square)
#   'neg_one' : negative 1   (red small square)
#
# filename : saved to ./figures
# ─────────────────────────────────────────────────────────────────────────────

def make_algebra_tiles(expression, filename='algebra_tiles.png'):
    import matplotlib.patches as patches

    C = {
        'x2':'#5bacd6','neg_x2':'#e05c5c',
        'y2':'#5bacd6','neg_y2':'#e05c5c',
        'xy':'#4dab82','neg_xy':'#e05c5c',
        'x':'#5bacd6','neg_x':'#e05c5c',
        'y':'#9b59b6','neg_y':'#e05c5c',
        'one':'#3a3ab0','neg_one':'#e05c5c',
    }
    L = {
        'x2':r'$x^2$','neg_x2':r'$-x^2$',
        'y2':r'$y^2$','neg_y2':r'$-y^2$',
        'xy':r'$x \cdot y$','neg_xy':r'$-x \cdot y$',
        'x':r'$x$','neg_x':r'$-x$',
        'y':r'$y$','neg_y':r'$-y$',
        'one':r'$1$','neg_one':r'$-1$',
    }
    D = {
        'x2':(1.0,1.0),'neg_x2':(1.0,1.0),
        'y2':(1.0,1.0),'neg_y2':(1.0,1.0),
        'xy':(0.75,0.75),'neg_xy':(0.75,0.75),
        'x':(0.28,1.0),'neg_x':(0.28,1.0),
        'y':(0.28,1.0),'neg_y':(0.28,1.0),
        'one':(0.28,0.28),'neg_one':(0.28,0.28),
    }

    order = ['x2','neg_x2','y2','neg_y2','xy','neg_xy',
             'x','neg_x','y','neg_y','one','neg_one']

    tiles = []
    for kind in order:
        for _ in range(expression.get(kind, 0)):
            tiles.append(kind)

    if not tiles:
        return

    gap       = 0.15
    pad       = 0.35
    max_row_w = 5.5

    rows    = []
    cur_row = []
    cur_w   = 0.0

    for kind in tiles:
        tw = D[kind][0]
        if cur_w + tw + gap > max_row_w and cur_row:
            rows.append(cur_row)
            cur_row = [kind]
            cur_w   = tw + gap
        else:
            cur_row.append(kind)
            cur_w += tw + gap
    if cur_row:
        rows.append(cur_row)

    row_heights = [max(D[k][1] for k in row) for row in rows]
    total_h = sum(row_heights) + gap * (len(rows)-1) + pad * 2
    total_w = max_row_w + pad * 2

    fig, ax = plt.subplots(figsize=(total_w, total_h))
    fig.patch.set_facecolor('white')
    ax.set_xlim(0, total_w)
    ax.set_ylim(0, total_h)
    ax.axis('off')

    y_cursor = total_h - pad

    for r, row in enumerate(rows):
        rh = row_heights[r]
        y_cursor -= rh
        x_cursor  = pad

        for kind in row:
            tw, th = D[kind]
            rect = patches.FancyBboxPatch(
                (x_cursor, y_cursor + (rh-th)/2), tw, th,
                boxstyle='round,pad=0.02',
                linewidth=2.0, edgecolor='white', facecolor=C[kind]
            )
            ax.add_patch(rect)
            fs = 13 if tw >= 0.7 else 9
            ax.text(x_cursor + tw/2,
                    y_cursor + (rh-th)/2 + th/2,
                    L[kind],
                    ha='center', va='center',
                    fontsize=fs, color='white',
                    fontfamily='Times New Roman', style='italic')
            x_cursor += tw + gap

        y_cursor -= gap

    path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(path, dpi=144, bbox_inches='tight')
    print(f'Saved: {path}')

# ─────────────────────────────────────────────────────────────────────────────
# PASTE YOUR GRAPH CODE BELOW THIS LINE
# ─────────────────────────────────────────────────────────────────────────────



# Unit 1 Assessment Bank graph-generation blocks
# All figures use graph_tool.py functions. Styling is not overridden.

def _save_standard_blank(filename):
    fig, ax = plt.subplots(figsize=(3.5, 3.5))
    fig.patch.set_facecolor('white')
    make_standard_graph(ax, [], title='')
    save_graph(fig, filename)
    plt.close(fig)

_save_standard_blank('u1_bank_s1_coordinate_blank_sq_v1.png')
_save_standard_blank('u1_bank_s5_coordinate_blank_sq_v1.png')

fig, ax = plt.subplots(figsize=(3.5, 3.5))
fig.patch.set_facecolor('white')
make_standard_graph(ax, [
    {'expr': lambda x: 2*x + 1, 'deriv': lambda x: 0*x + 2, 'color': 'steelblue', 'label': None}
], title='')
save_graph(fig, 'u1_bank_s1_evidence_line_sq_v1.png')
plt.close(fig)

fig, ax = plt.subplots(figsize=(3.5, 3.5))
fig.patch.set_facecolor('white')
make_context_graph(ax, [
    {'expr': lambda x: 5 + 4*x, 'deriv': lambda x: 0*x + 4, 'color': 'steelblue', 'label': None}
], xmin=0, xmax=10, ymin=0, ymax=50, xlabel='Tickets', ylabel='Cost', title='')
save_graph(fig, 'u1_bank_s1_context_cost_sq_v1.png')
plt.close(fig)

fig, ax = plt.subplots(figsize=(3.5, 3.5))
fig.patch.set_facecolor('white')
make_scatter_plot(ax, [0,1,1,2,3], [3,4,6,7,8], xmin=0, xmax=4, ymin=0, ymax=10, color='steelblue', point_size=40, line_of_best_fit=False, xlabel='Input', ylabel='Output', title='')
save_graph(fig, 'u1_bank_s2_relation_points_sq_v1.png')
plt.close(fig)

fig, ax = plt.subplots(figsize=(3.5, 3.5))
fig.patch.set_facecolor('white')
make_standard_graph(ax, [
    {'expr': lambda x: -x + 4, 'deriv': lambda x: 0*x - 1, 'color': 'steelblue', 'label': None}
], title='')
save_graph(fig, 'u1_bank_s2_function_line_sq_v1.png')
plt.close(fig)

fig = make_2x2_grid([
    [{'expr': lambda x: x + 1, 'deriv': lambda x: 0*x + 1, 'color': 'steelblue', 'label': None}],
    [{'expr': lambda x: x**2 - 4, 'deriv': lambda x: 2*x, 'color': 'steelblue', 'label': None}],
    [{'expr': lambda x: 2**x, 'deriv': lambda x: np.log(2)*2**x, 'color': 'steelblue', 'label': None}],
    [{'expr': lambda x: np.abs(x) - 3, 'deriv': lambda x: np.sign(x), 'color': 'steelblue', 'label': None}],
], titles=['A','B','C','D'])
save_graph(fig, 'u1_bank_s3_family_grid_sq_v1.png')
plt.close(fig)

fig, ax = plt.subplots(figsize=(3.5, 3.5))
fig.patch.set_facecolor('white')
make_context_graph(ax, [
    {'expr': lambda x: 2*(1.45**x), 'deriv': lambda x: 2*np.log(1.45)*(1.45**x), 'color': 'steelblue', 'label': None}
], xmin=0, xmax=8, ymin=0, ymax=40, xlabel='Step', ylabel='Output', title='')
save_graph(fig, 'u1_bank_s3_exp_context_sq_v1.png')
plt.close(fig)

fig = make_2x1_grid([
    [{'expr': lambda x: np.abs(x+2) - 3, 'deriv': lambda x: np.sign(x+2), 'color': 'steelblue', 'label': None}],
    [{'expr': lambda x: (x-1)**2 - 4, 'deriv': lambda x: 2*(x-1), 'color': 'steelblue', 'label': None}],
], titles=['A','B'])
save_graph(fig, 'u1_bank_s3_abs_quad_sq_v1.png')
plt.close(fig)

make_rectangle_model([r'$2x$', r'$3$'], [r'$x$', r'$5$'], [[r'$2x^2$', ''], ['', '']], 'u1_bank_s4_rect_blank_sq_v1.png')
make_rectangle_model([r'$x$', r'$4$'], [r'$x$', r'$6$'], [[r'$x^2$', r'$6x$'], [r'$4x$', r'$20$']], 'u1_bank_s4_rect_mismatch_sq_v1.png')
make_diamond(r'$-24$', '', '', r'$2$', 'u1_bank_s4_diamond_sq_v1.png')

fig, ax = plt.subplots(figsize=(3.5, 3.5))
fig.patch.set_facecolor('white')
make_context_graph(ax, [
    {'expr': lambda x: 15 + 2*x, 'deriv': lambda x: 0*x + 2, 'color': 'steelblue', 'label': 'Plan A'},
    {'expr': lambda x: 5 + 4*x, 'deriv': lambda x: 0*x + 4, 'color': 'firebrick', 'label': 'Plan B'},
], xmin=0, xmax=10, ymin=0, ymax=45, xlabel='Items', ylabel='Cost', title='')
save_graph(fig, 'u1_bank_s5_balance_context_sq_v1.png')
plt.close(fig)


# Unit 1 Section 2 notes graph-generation blocks
# All figures use graph_tool.py functions. Styling is only used to mark requested points.

def _mark_point(ax, x, y, label):
    ax.plot([x], [y], 'o', color='firebrick', markersize=6, zorder=5)
    ax.text(x+0.2, y+0.4, label, fontfamily='Times New Roman', fontsize=10, color='firebrick')

fig, ax = plt.subplots(figsize=(3.5, 3.5))
fig.patch.set_facecolor('white')
make_standard_graph(ax, [{'expr': lambda x: 2*x+1, 'deriv': lambda x: 0*x+2, 'color': 'steelblue', 'label': None}], title='')
_mark_point(ax, 3, 7, '(3,7)')
save_graph(fig, 'u1_s2_mn1_eval_f3.png')
plt.close(fig)

fig, ax = plt.subplots(figsize=(3.5, 3.5))
fig.patch.set_facecolor('white')
make_context_graph(ax, [
    {'expr': lambda x: 2+3*x, 'deriv': lambda x: 0*x+3, 'color': 'steelblue', 'label': 'rule'},
    {'expr': lambda x: 0*x+17, 'deriv': lambda x: 0*x, 'color': 'firebrick', 'label': 'target'}
], xmin=0, xmax=8, ymin=0, ymax=25, xlabel='Rounds', ylabel='Output', title='')
_mark_point(ax, 5, 17, '(5,17)')
save_graph(fig, 'u1_s2_mn2_rule_solve.png')
plt.close(fig)

fig, ax = plt.subplots(figsize=(3.5, 3.5))
fig.patch.set_facecolor('white')
make_context_graph(ax, [{'expr': lambda x: np.sqrt(x+4), 'deriv': lambda x: 1/(2*np.sqrt(x+4+1e-9)), 'color': 'steelblue', 'label': None}], xmin=-4, xmax=12, ymin=0, ymax=5, xlabel='x', ylabel='g(x)', title='')
for xx, yy in [(-4,0),(0,2),(5,3),(12,4)]:
    _mark_point(ax, xx, yy, '')
save_graph(fig, 'u1_s2_mn3_sqrt_table.png')
plt.close(fig)
