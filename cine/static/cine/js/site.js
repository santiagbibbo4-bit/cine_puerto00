// Mejoras de interfaz sin dependencias. El sitio funciona sin JavaScript (el carrusel usa scroll nativo).
(function () {
  'use strict';

  // Carrusel: botones, flechas del teclado y avance automático (se pausa al interactuar o si el usuario prefiere menos movimiento).
  document.querySelectorAll('[data-carousel]').forEach(function (root) {
    var track = root.querySelector('.slides');
    var slides = root.querySelectorAll('.slide');
    if (!track || slides.length < 2) return;
    var timer = null;

    function go(dir) {
      var w = track.clientWidth;
      var max = track.scrollWidth - w;
      var next = track.scrollLeft + dir * w;
      if (next > max + 2) next = 0;
      if (next < 0) next = max;
      track.scrollTo({ left: next, behavior: 'smooth' });
    }
    root.querySelectorAll('.car-btn').forEach(function (b) {
      b.addEventListener('click', function () {
        go(Number(b.dataset.dir));
        stop();
      });
    });
    track.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight') { go(1); stop(); e.preventDefault(); }
      if (e.key === 'ArrowLeft') { go(-1); stop(); e.preventDefault(); }
    });
    function start() {
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      timer = setInterval(function () { go(1); }, 6000);
    }
    function stop() { clearInterval(timer); timer = null; }
    ['mouseenter', 'focusin', 'touchstart'].forEach(function (ev) { root.addEventListener(ev, stop, { passive: true }); });
    start();
  });

  // Confirmación para acciones delicadas (CSP no permite onclick inline).
  document.addEventListener('click', function (e) {
    var el = e.target.closest('[data-confirm]');
    if (el && !window.confirm(el.getAttribute('data-confirm'))) e.preventDefault();
  });

  // Cierra el menú móvil al elegir un enlace.
  var toggle = document.getElementById('nav-toggle');
  if (toggle) {
    document.querySelectorAll('.main-nav a').forEach(function (a) {
      a.addEventListener('click', function () { toggle.checked = false; });
    });
  }
})();
