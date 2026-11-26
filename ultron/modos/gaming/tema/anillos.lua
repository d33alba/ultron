-- Anillos CPU, RAM y GPU. Conky con Cairo y superficie X11.
require 'cairo'
pcall(require, 'cairo_xlib')

function conky_anillos()
    if conky_window == nil or cairo_xlib_surface_create == nil then
        return
    end
    local superficie = cairo_xlib_surface_create(conky_window.display,
        conky_window.drawable, conky_window.visual, conky_window.width, conky_window.height)
    local cr = cairo_create(superficie)
    local muestras = {
        {tonumber(conky_parse('${cpu}')) or 0, 0.22, 1, 0.08},
        {tonumber(conky_parse('${memperc}')) or 0, 0, 0.94, 1},
        {tonumber(conky_parse([=[${execi 3 @@hud@@ gpu}]=])) or 0, 1, 0, 0.9}
    }
    for i, muestra in ipairs(muestras) do
        local radio, inicio = 35 - (i - 1) * 9, -math.pi / 2
        cairo_set_line_width(cr, 5)
        cairo_set_source_rgba(cr, muestra[2], muestra[3], muestra[4], 0.2)
        cairo_arc(cr, 165, 111, radio, inicio, inicio + 2 * math.pi)
        cairo_stroke(cr)
        cairo_set_source_rgba(cr, muestra[2], muestra[3], muestra[4], 1)
        local valor = math.min(100, math.max(0, muestra[1]))
        cairo_arc(cr, 165, 111, radio, inicio, inicio + 2 * math.pi * valor / 100)
        cairo_stroke(cr)
    end
    cairo_destroy(cr)
    cairo_surface_destroy(superficie)
end

