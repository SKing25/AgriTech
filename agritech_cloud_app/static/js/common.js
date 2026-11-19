/* Utilidades compartidas por el tablero y la vista de detalle de AgriTech Precision. */
(function () {
  'use strict';

  var ESPECIALES = {
    OPTIMO: 'Óptimo',
    CRITICA: 'Crítica',
    ERROR_VALVULA: 'Error de válvula',
    ACTIVO: 'Activo',
    INACTIVO: 'Inactivo'
  };
  var ROLES = {
    GESTOR_SENSORES: 'Gestor de sensores',
    TECNICO_AGRICOLA: 'Técnico agrícola',
    ADMINISTRADOR: 'Administrador'
  };

  /* Valor de enumeración -> texto legible (OBJETIVO_ALCANZADO -> "Objetivo alcanzado"). */
  function etiqueta(valor) {
    if (valor === null || valor === undefined || valor === '') return '';
    var v = String(valor);
    if (ESPECIALES[v]) return ESPECIALES[v];
    var t = v.replace(/_/g, ' ').toLowerCase();
    return t.charAt(0).toUpperCase() + t.slice(1);
  }

  function etiquetaRol(rol) { return ROLES[rol] || rol || ''; }

  /* Escapa HTML. Conserva el 0 (la versión anterior lo convertía en cadena vacía). */
  function escapeHtml(txt) {
    if (txt === null || txt === undefined) return '';
    return String(txt)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  /* ---------- Tema claro / oscuro ---------- */
  function actualizarBotonTema() {
    var btn = document.getElementById('btnTema');
    if (!btn) return;
    var oscuro = document.documentElement.classList.contains('dark');
    btn.textContent = oscuro ? 'Modo claro' : 'Modo oscuro';
    btn.setAttribute('aria-pressed', oscuro ? 'true' : 'false');
  }

  function aplicarTemaInicial() {
    var html = document.documentElement;
    var guardado = null;
    try { guardado = localStorage.getItem('agritech-theme'); } catch (e) {}
    if (guardado === 'light') html.classList.remove('dark');
    else html.classList.add('dark');
    actualizarBotonTema();
  }

  function alternarTema() {
    var html = document.documentElement;
    html.classList.toggle('dark');
    try { localStorage.setItem('agritech-theme', html.classList.contains('dark') ? 'dark' : 'light'); } catch (e) {}
    actualizarBotonTema();
    /* Los gráficos SVG leen sus colores de variables CSS: basta con repintar. */
    document.dispatchEvent(new CustomEvent('agritech:tema'));
  }

  /* ---------- Avisos (reemplazan a alert()) ---------- */
  var toastTimer = null;
  function showToast(msg, tipo) {
    var el = document.getElementById('toast');
    if (!el) return;
    el.textContent = msg;
    el.className = 'toast' + (tipo === 'error' ? ' toast-error' : '');
    el.setAttribute('role', tipo === 'error' ? 'alert' : 'status');
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.hidden = true; }, tipo === 'error' ? 4500 : 2200);
  }

  /* ---------- Llamadas a la API ---------- */
  async function apiJson(url, method, body) {
    var res;
    try {
      res = await fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined
      });
    } catch (e) {
      showToast('Sin conexión con el servidor. Intente de nuevo.', 'error');
      return null;
    }
    var data = null;
    try { data = await res.json(); } catch (e) { /* respuesta sin JSON */ }
    if (!res.ok) {
      var detalle = (data && data.error) ? data.error : 'Operación rechazada';
      showToast('Error ' + res.status + ': ' + detalle, 'error');
      return null;
    }
    return data;
  }

  /* ---------- Indicador "en vivo" y sondeo ---------- */
  function marcarConexion(ok) {
    var badge = document.getElementById('liveBadge');
    var txt = document.getElementById('liveText');
    if (!badge || !txt) return;
    badge.classList.toggle('live-off', !ok);
    txt.textContent = ok ? 'En vivo · 2.5 s' : 'Sin conexión · reintentando';
  }

  /* Sondeo periódico. Se pausa con la pestaña oculta para no gastar invocaciones serverless. */
  function iniciarSondeo(fn, ms) {
    var activo = true;
    async function tick() {
      if (document.hidden) return;
      try { await fn(); marcarConexion(true); } catch (e) { marcarConexion(false); }
    }
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden && activo) tick();
    });
    return setInterval(tick, ms);
  }

  window.AG = {
    etiqueta: etiqueta,
    etiquetaRol: etiquetaRol,
    escapeHtml: escapeHtml,
    apiJson: apiJson,
    marcarConexion: marcarConexion,
    iniciarSondeo: iniciarSondeo
  };
  window.aplicarTemaInicial = aplicarTemaInicial;
  window.alternarTema = alternarTema;
  window.showToast = showToast;
  window.escapeHtml = escapeHtml;

  document.addEventListener('DOMContentLoaded', actualizarBotonTema);
})();
