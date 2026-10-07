(() => {
  const navToggle = document.querySelector('[data-nav-toggle]');
  const nav = document.querySelector('[data-nav]');
  const backdrop = document.querySelector('[data-sidebar-backdrop]');
  document.querySelectorAll('[data-nav-toggle]').forEach(toggle => toggle.addEventListener('click', () => {
    nav?.classList.toggle('open');
    backdrop?.classList.toggle('open', nav?.classList.contains('open'));
  }));
  backdrop?.addEventListener('click', () => { nav?.classList.remove('open'); backdrop.classList.remove('open'); });
  document.querySelectorAll('.channel-nav a').forEach(link => link.addEventListener('click', () => {
    if (window.innerWidth <= 900) { nav?.classList.remove('open'); backdrop?.classList.remove('open'); }
  }));

  const sidebarSearch = document.getElementById('sidebar-map-search');
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      if (window.innerWidth <= 900) {
        nav?.classList.add('open');
        backdrop?.classList.add('open');
      }
      window.setTimeout(() => sidebarSearch?.focus(), 60);
    }
  });

  document.querySelectorAll('.flash button').forEach(button => {
    button.addEventListener('click', () => button.parentElement.remove());
  });
  window.setTimeout(() => document.querySelectorAll('.flash').forEach(el => el.remove()), 6000);

  const copy = async (text, button) => {
    try {
      await navigator.clipboard.writeText(text.trim());
      const old = button.textContent;
      button.textContent = 'Copied ✓';
      window.setTimeout(() => button.textContent = old, 1500);
    } catch (_) {
      const area = document.createElement('textarea');
      area.value = text.trim();
      document.body.appendChild(area); area.select(); document.execCommand('copy'); area.remove();
      const old = button.textContent; button.textContent = 'Copied ✓';
      window.setTimeout(() => button.textContent = old, 1500);
    }
  };
  document.querySelectorAll('[data-copy]').forEach(button => {
    button.addEventListener('click', () => {
      const target = document.querySelector(button.dataset.copy);
      if (target) copy(target.textContent, button);
    });
  });
  document.querySelectorAll('[data-copy-text]').forEach(button => {
    button.addEventListener('click', () => copy(button.dataset.copyText, button));
  });

  const tabs = document.querySelectorAll('[data-tab]');
  tabs.forEach(tab => tab.addEventListener('click', () => {
    tabs.forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(x => x.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(tab.dataset.tab)?.classList.add('active');
  }));

  if (window.SQUADFINDER_LIVE_ROOMS) {
    const refresh = async () => {
      try {
        const response = await fetch('/api/rooms', {headers: {'Accept':'application/json'}});
        if (!response.ok) return;
        const data = await response.json();
        const count = document.getElementById('room-count');
        if (count) count.textContent = data.rooms.length;
        const ids = new Set(data.rooms.map(room => String(room.id)));
        document.querySelectorAll('[data-room-id]').forEach(card => {
          if (!ids.has(card.dataset.roomId)) card.style.opacity = '.45';
        });
      } catch (_) {}
    };
    window.setInterval(refresh, 10000);
  }
})();
