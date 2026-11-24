// Visor: flechas o espacio para avanzar (primero los fragmentos, luego la diapositiva),
// N para notas del presentador, F para pantalla completa, Inicio/Fin para ir al principio o al final.
// La diapositiva actual queda en la URL (#3), así se puede compartir un enlace a una diapositiva.
(function () {
  const stage = document.getElementById('stage');
  const slides = Array.from(stage.children).filter(el => el.tagName === 'SECTION');
  const notes = document.getElementById('notes');
  const counter = document.getElementById('counter');
  let cur = 0, step = 0;

  function fit() {
    const s = Math.min(innerWidth / 1920, innerHeight / 1080);
    stage.style.transform = `scale(${s}) translate(-960px, -540px)`;
  }
  function steps(sl) {
    const idx = Array.from(sl.querySelectorAll('.fragment')).map(f => +(f.dataset.fragmentIndex || 0));
    return idx.length ? Math.max(...idx) : 0;
  }
  function render() {
    slides.forEach((sl, i) => sl.classList.toggle('current', i === cur));
    const sl = slides[cur];
    sl.querySelectorAll('.fragment').forEach(f => f.classList.toggle('visible', +(f.dataset.fragmentIndex || 0) <= step));
    const aside = sl.querySelector('aside');
    notes.textContent = aside ? aside.textContent.trim() : '';
    counter.textContent = `${cur + 1} / ${slides.length}`;
    history.replaceState(null, '', '#' + (cur + 1));
  }
  function go(i, atEnd) {
    cur = Math.max(0, Math.min(slides.length - 1, i));
    step = atEnd ? steps(slides[cur]) : 0;
    render();
  }
  function next() { if (step < steps(slides[cur])) { step++; render(); } else if (cur < slides.length - 1) go(cur + 1); }
  function prev() { if (step > 0) { step--; render(); } else if (cur > 0) go(cur - 1, true); }

  // Recorte de fotos (data-crop="escala posX posY"): acerca la imagen sobre el punto indicado.
  document.querySelectorAll('img[data-crop]').forEach(img => {
    const [scale, x, y] = img.dataset.crop.split(/\s+/);
    img.style.objectFit = 'cover';
    img.style.objectPosition = `${x} ${y}`;
    const wrap = document.createElement('div');
    wrap.className = img.className; wrap.style.cssText = img.getAttribute('style'); wrap.style.overflow = 'hidden';
    img.removeAttribute('class'); img.setAttribute('style', `width:100%;height:100%;display:block;object-fit:cover;object-position:${x} ${y};transform:scale(${scale});transform-origin:${x} ${y}`);
    img.parentNode.insertBefore(wrap, img); wrap.appendChild(img);
  });

  addEventListener('keydown', e => {
    if (['ArrowRight', 'ArrowDown', 'PageDown', ' ', 'Enter'].includes(e.key)) { e.preventDefault(); next(); }
    else if (['ArrowLeft', 'ArrowUp', 'PageUp', 'Backspace'].includes(e.key)) { e.preventDefault(); prev(); }
    else if (e.key === 'Home') go(0);
    else if (e.key === 'End') go(slides.length - 1);
    else if (e.key === 'n' || e.key === 'N') document.body.classList.toggle('show-notes');
    else if (e.key === 'f' || e.key === 'F') { document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen(); }
  });
  addEventListener('click', e => { if (!e.target.closest('#notes')) (e.clientX < innerWidth / 3 ? prev : next)(); });
  addEventListener('hashchange', () => go((parseInt(location.hash.slice(1), 10) || 1) - 1));
  addEventListener('resize', fit);
  fit();
  go((parseInt(location.hash.slice(1), 10) || 1) - 1);
})();
