"""
Módulo que contiene la interfaz gráfica para las curvas IV.

Las acciones de análisis (Vbr, Qr, "Draw complete") delegan en
``analysis.iv_analysis``. Las mediciones de adquisición se hacen a
través de ``DAQGUIFunctions.start_iv_full`` (ver daq_gui_main.py).

Analysis behaviour:

  * **Vbr** plots the negative section of the IV curve with
    the (dI/dV)/I derivative on a secondary y-axis (red), and
    marks the calculated Vbr point on both the IV curve and
    the derivative minimum.

  * **Qr** plots the positive section of the IV curve with
    two red draggable dots at the min / max of the positive
    section. The user can drag the dots along the curve to
    pick a custom voltage range; pressing the Qr button again
    re-fits the segment between the new endpoints.

  * **Draw complete** plots the full IV curve so the user
    sees the whole SiPM response (positive + negative).

The QR interactive plot stores the (v, i) coordinates of the
two draggable dots on ``self.iv_qr_markers`` and the live
endpoints on ``self.iv_qr_endpoints`` so the calculation can
read them on each Qr press.
"""
import customtkinter as ctk
import numpy as np


def _parse_iv_aux(self):
    v_str = self.v_values_aux.get()
    i_str = self.i_values_aux.get()
    if not v_str or not i_str:
        return None, None
    v = [float(x) for x in v_str.split(", ")]
    i = [float(x) for x in i_str.split(", ")]
    return v, i


def _get_canvas(self):
    """Return (figure, axes) for the IV plot, rebuilding the
    canvas if the user has never run an acquisition yet."""
    fig = self.canvas.figure
    ax = fig.gca()
    return fig, ax


def _do_vbr(self):
    v, i = _parse_iv_aux(self)
    if v is None:
        print("Necesitas realizar algun analisis primero..")
        return
    result = self.gui_funcs.vbr_for(v, i)
    if not result["ok"]:
        print(result["message"])
        return
    self.vbr_Output.configure(state="normal")
    self.vbr_Output.delete("1.0", "end")
    self.vbr_Output.insert("0.0", f"{result['max_x']:.4g} V")
    self.vbr_Output.configure(state="disabled")

    # Remember the Vbr point so ``_do_complete`` can keep
    # the red dot on the negative section when the user
    # switches to the full-curve view.
    self.iv_vbr_point = (result["max_x"], result["max_y"])

    _, ax = _get_canvas(self)
    self.gui_funcs.plot_vbr(
        ax,
        v_filtered=result["v_filtered"],
        i_filtered=result["i_filtered"],
        vbr_point=(result["max_x"], result["max_y"]),
        dydx_over_y=result["dydx_over_y"],
        v_for_ratio=result["v_for_ratio"],
    )
    try:
        self.canvas.draw()
        self.canvas.flush_events()
    except Exception:
        pass


def _do_qr(self):
    """QR analysis with user-movable endpoints.

    First press: plots the positive section with two red
    draggable dots at the min and max of the positive section,
    zoomed in. The user drags the markers to pick the segment
    they want to fit, then presses Qr again. This is the
    classic 'select first, fit on demand' workflow that lets
    the user avoid the legacy failure mode where the default
    range picked the wrong segment.

    Subsequent presses: re-fit the segment between the
    endpoints the user has positioned. The fit uses the
    current endpoint positions, not the original defaults.
    """
    v, i = _parse_iv_aux(self)
    if v is None:
        print("Necesitas realizar algun analisis primero..")
        return

    # Cache the positive section so the click that just
    # shows the markers and the click that fits the segment
    # both share the same data.
    pos_mask = np.asarray(v) > 0.01
    v_pos = np.asarray(v, dtype=float)[pos_mask]
    i_pos = np.asarray(i, dtype=float)[pos_mask]
    if v_pos.size < 2:
        print("No hay suficientes valores positivos para QR.")
        return

    _, ax = _get_canvas(self)

    # First press: no markers yet. Render the positive section
    # with two pickable endpoints and wait for the user to
    # either press Qr again (we will fit between the current
    # endpoint positions) or drag the markers first.
    if getattr(self, "iv_qr_endpoints", None) is None:
        # Initial endpoints at the curve bounds. The user can
        # drag them anywhere along the curve before pressing
        # Qr again to compute the fit.
        self.iv_qr_endpoints = (float(v_pos[0]), float(v_pos[-1]))
        self.gui_funcs.plot_qr_initial(ax, v_pos, i_pos)
        self._install_qr_marker_drag_handlers()
        try:
            self.canvas.draw()
            self.canvas.flush_events()
        except Exception:
            pass
        return

    # Subsequent press: fit between the current endpoint
    # positions. If the user has dragged the markers, those
    # new positions drive the fit; if not, the initial
    # endpoints above are used.
    v_range = self.iv_qr_endpoints
    result = self.gui_funcs.qr_for(v, i, v_range=v_range)
    if not result["ok"]:
        print(result["message"])
        return
    self.qr_Output.configure(state="normal")
    self.qr_Output.delete("1.0", "end")
    self.qr_Output.insert("0.0", f"{result['qr_value']} Ω")
    self.qr_Output.configure(state="disabled")
    self.gui_funcs.plot_qr_with_fit(
        ax, result["v_positive"], result["i_positive"],
        result["v_fit"], result["i_fit"],
    )
    try:
        self.canvas.draw()
        self.canvas.flush_events()
    except Exception:
        pass


def _install_qr_marker_drag_handlers(self) -> None:
    """Install a PickEvent + MotionNotifyEvent handler on the
    matplotlib canvas so the user can drag the two QR endpoint
    markers along the curve.

    We snapshot the two markers on ``self.iv_qr_markers``
    (the Line2D objects returned by matplotlib). When the
    user clicks a marker, a Motion handler snaps the marker
    to the nearest curve point until they release the mouse
    button. Releasing the button removes the motion handler
    so the plot goes back to its normal idle behaviour.
    """
    if getattr(self, "_qr_drag_handlers_installed", False):
        return
    ax = self.canvas.figure.gca()

    def _on_pick(event):
        # ``event.artist`` is the Line2D the user picked. We
        # only react to the two QR markers; ignore anything
        # else (axis spines, the curve itself, etc.).
        markers = getattr(self, "iv_qr_markers", None)
        if markers is None or event.artist not in markers:
            return
        idx = markers.index(event.artist)
        # Cache the underlying curve data for snapping.
        line = None
        for line_artist in ax.get_lines():
            if line_artist.get_label() == "IV (positiva)":
                line = line_artist
                break
        if line is None:
            return
        curve_x = np.asarray(line.get_xdata(), dtype=float)
        curve_y = np.asarray(line.get_ydata(), dtype=float)

        def _on_motion(ev):
            if ev.inaxes is not ax:
                return
            # Snap the picked marker to the closest point on
            # the IV curve so the user cannot drag it off the
            # data.
            snap_idx = int(np.argmin(np.abs(curve_x - ev.xdata)))
            markers[idx].set_data([curve_x[snap_idx]], [curve_y[snap_idx]])
            self.canvas.draw_idle()

        def _on_release(_ev):
            # Detach the motion handler and refresh the
            # endpoint snapshot so the next Qr press uses the
            # new range.
            self.canvas.mpl_disconnect(motion_cid)
            self.canvas.mpl_disconnect(release_cid)
            self.iv_qr_endpoints = (
                markers[0].get_xdata()[0], markers[1].get_xdata()[0],
            )

        motion_cid = self.canvas.mpl_connect(
            "motion_notify_event", _on_motion,
        )
        release_cid = self.canvas.mpl_connect(
            "button_release_event", _on_release,
        )

    self.canvas.mpl_connect("pick_event", _on_pick)
    self._qr_drag_handlers_installed = True

    # We need to capture the markers after the next draw.
    # plot_qr_initial sets them with ``picker=5``; we grab
    # them once via a deferred call.
    def _grab_markers():
        red_lines = [
            line for line in ax.get_lines()
            if line.get_marker() == "o"
            and line.get_color() == "r"
            and line.get_picker() is not None
        ]
        if red_lines:
            self.iv_qr_markers = red_lines
    self.after(50, _grab_markers)


def _do_complete(self):
    v, i = _parse_iv_aux(self)
    if v is None:
        print("Necesitas realizar algun analisis primero..")
        return
    _, ax = _get_canvas(self)
    vbr_point = getattr(self, "iv_vbr_point", None)
    self.gui_funcs.plot_complete(ax, v, i, vbr_point=vbr_point)
    try:
        self.canvas.draw()
        self.canvas.flush_events()
    except Exception:
        pass


def _reset_qr_state(self) -> None:
    """Clear the QR drag state so the next Qr press starts
    fresh (default endpoints, default range). Also drops the
    cached Vbr point so a fresh IV curve does not show a
    stale red dot on the negative section."""
    self.iv_qr_endpoints = None
    self.iv_qr_markers = None
    self._qr_drag_handlers_installed = False
    self.iv_vbr_point = None


def iv_update_connected(self) -> None:
    """Re-read the SMU connection and repaint the IV tab header.

    Called from the Connect tab success / disconnect handlers
    so the "SMU: <*IDN?>" line always reflects the live
    state. When no SMU is connected the line shows a grey
    placeholder and the Start button is disabled.
    """
    label = getattr(self, "iv_smu_label", None)
    if label is None:
        return
    card = (self.connect_cards.get("smu")
            if isinstance(getattr(self, "connect_cards", None), dict) else None)
    conn = card.get("connection") if isinstance(card, dict) else None
    idn = card.get("idn") if isinstance(card, dict) else None
    if conn is not None and idn:
        label.configure(
            text=f"SMU: {idn}", text_color="#2ea043",
        )
    else:
        label.configure(
            text="SMU: (not connected)", text_color="#a0a0a0",
        )


def _iv_on_channel_toggle(self, channel: int) -> None:
    """No-op kept for back-compat with the old check-box API.

    The radio buttons share a single StringVar, so the
    selection is automatically mutually exclusive and we
    never need to clear the other option. The argument is
    ignored; the helper is referenced from the old test
    suite and from any external code that may have wired
    the legacy check-box command callback.
    """
    return None


def iv_selected_channel(self) -> int:
    """Return the SMU channel the user selected (1 or 2).

    Reads the radio-button StringVar. Defaults to 1 when
    the radio group has not been built yet (older App
    instances that predate the radio refactor) or when
    the value is unexpected. The returned integer is passed
    to the adapter as ``channel=...`` and substituted into
    the ``(@N)`` token of the :init and :FETCh commands.
    """
    var = getattr(self, "selected_channelIV", None)
    if var is None:
        return 1
    return 2 if var.get() == "CH2" else 1


def setting_iv(self):
    """
    Construye la pestaña IV Curves (DAQ + Analysis).
    """
    # create tabview
    self.tabviewIV = ctk.CTkTabview(self.tabview.tab("IV Curves"), width=100)
    self.tabviewIV.grid(row=0, column=0, padx=(5, 5), pady=(5, 5), sticky="nsew")
    self.tabviewIV.add("DAQ")
    self.tabviewIV.add("Analysis")
    self.tabviewIV.tab("DAQ").grid_columnconfigure(0, weight=0)
    self.tabviewIV.tab("DAQ").grid_columnconfigure(1, weight=3)
    self.tabviewIV.tab("DAQ").grid_rowconfigure(0, weight=1)
    self.tabviewIV.tab("Analysis").grid_columnconfigure(0, weight=0)
    self.tabviewIV.tab("Analysis").grid_columnconfigure(1, weight=3)
    self.tabviewIV.tab("Analysis").grid_rowconfigure(0, weight=1)

    # IV Curves tab settings DAQ
    self.optionsIV = ctk.CTkFrame(self.tabviewIV.tab("DAQ"))
    self.optionsIV.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    # The legacy SMU / Classic selector was removed; the SMU
    # card in the Connect tab is now the only way to choose the
    # source. We show the raw ``*IDN?`` of the connected SMU
    # (or a placeholder) so the user always knows which
    # instrument will be driven when they press Start.
    self.iv_smu_label = ctk.CTkLabel(
        self.optionsIV, text="SMU: (not connected)",
        anchor="w", font=("", 12, "bold"), text_color="#a0a0a0",
    )
    self.iv_smu_label.grid(row=0, column=0, padx=20, pady=(20, 0), sticky="w")
    # Back-compat attribute: legacy code paths and tests still
    # read ``self.options.get()`` to decide what to do. There
    # is no other SMU path today, so we hard-code "SMU".
    self.options = ctk.CTkOptionMenu(
        self.optionsIV, dynamic_resizing=False, values=["SMU"],
    )
    self.options.set("SMU")
    self.options.grid(row=0, column=1, padx=20, pady=(20, 0))
    self.options.grid_remove()

    # Channel selector. The Keithley 2470 has two channels; we
    # let the user pick which one to drive. Mirrors the
    # Spectrum / Waveform layout: an opaque box with two
    # columns, each column holding one CTkRadioButton. Both
    # columns have weight=1 so the radios sit centred in
    # their respective cells, regardless of the optionsIV
    # width. The radios share a single StringVar so mutual
    # exclusion comes for free.
    self.selected_channelIV = ctk.StringVar(value="CH1")
    self.channels_frame_iv = ctk.CTkFrame(self.optionsIV)
    self.channels_frame_iv.grid(
        row=1, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="ew",
    )
    # Two equal-weight columns so the two radios end up
    # horizontally centred within the box (each radio
    # sits in the middle of its own cell).
    self.channels_frame_iv.grid_columnconfigure((0, 1), weight=1)
    self.ch1IV = ctk.CTkRadioButton(
        self.channels_frame_iv, text="CH1",
        variable=self.selected_channelIV, value="CH1",
    )
    self.ch1IV.grid(row=0, column=0, padx=0, pady=(10, 5))
    self.ch2IV = ctk.CTkRadioButton(
        self.channels_frame_iv, text="CH2",
        variable=self.selected_channelIV, value="CH2",
    )
    self.ch2IV.grid(row=0, column=1, padx=0, pady=(10, 5))

    self.iv_start = ctk.CTkLabel(self.optionsIV, text="Set voltage start:", anchor="w")
    self.iv_start.grid(row=2, column=0, padx=20, pady=(10, 0))
    self.vStart = ctk.CTkEntry(self.optionsIV, placeholder_text="1V defalut")
    self.vStart.grid(row=3, column=0, padx=20, pady=(0,5))

    self.iv_stop = ctk.CTkLabel(self.optionsIV, text="Set voltage stop:", anchor="w")
    self.iv_stop.grid(row=4, column=0, padx=20, pady=(5, 0))
    self.vStop = ctk.CTkEntry(self.optionsIV, placeholder_text="-40V defalut")
    self.vStop.grid(row=5, column=0, padx=20, pady=(0,5))

    self.iv_step = ctk.CTkLabel(self.optionsIV, text="Set voltage step:", anchor="w")
    self.iv_step.grid(row=6, column=0, padx=20, pady=(5, 0))
    self.vStep = ctk.CTkEntry(self.optionsIV, placeholder_text="0.05V defalut")
    self.vStep.grid(row=7, column=0, padx=20, pady=(0,5))

    self.start_button = ctk.CTkButton(self.optionsIV, text="Start", command=self.start_iv)
    self.start_button.grid(row=8, column=0, padx=20, pady=(15, 20), columnspan=2, sticky="s")

    # QR drag state and cached Vbr point. The interactive QR
    # plot uses two user-movable markers to define the fit
    # range; these attributes cache the current endpoints,
    # the marker artists, and the last computed Vbr point so
    # the next analysis press can read the new range without
    # re-prompting. Reset to None on every fresh acquisition
    # (see daq_gui_main._on_results -> _reset_qr_state).
    _reset_qr_state(self)

    self.plotIV = ctk.CTkFrame(self.tabview.tab("IV Curves"))
    self.plotIV.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
    self.plotIV.grid_rowconfigure(0, weight=1)
    self.plotIV.grid_columnconfigure(0, weight=1)

    # Analysis tab
    self.analysisIV = ctk.CTkFrame(self.tabviewIV.tab("Analysis"))
    self.analysisIV.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    self.vbr_button = ctk.CTkButton(self.analysisIV, text="Calculate Vbr", command=lambda: _do_vbr(self), width=120)
    self.vbr_button.grid(row=0, column=0, padx=(10), pady=(20,5))
    self.vbr_Output = ctk.CTkTextbox(self.analysisIV, width=90, height=30, activate_scrollbars=False)
    self.vbr_Output.grid(row=1, column=0, padx=(10), pady=(5,10))

    self.qr_button = ctk.CTkButton(self.analysisIV, text="Calculate Qr", command=lambda: _do_qr(self), width=120)
    self.qr_button.grid(row=2, column=0, padx=(10), pady=(10,5))
    self.qr_Output = ctk.CTkTextbox(self.analysisIV, width=90, height=30, activate_scrollbars=False)
    self.qr_Output.grid(row=3, column=0, padx=(10), pady=(5,5))

    self.complete_button = ctk.CTkButton(self.analysisIV, text="Draw complete", command=lambda: _do_complete(self), width=120)
    self.complete_button.grid(row=4, column=0, padx=(10), pady=(20,5))
