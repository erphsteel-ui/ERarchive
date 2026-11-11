'use strict';
(function(){
 let stored=null;try{stored=localStorage.getItem('er_theme')}catch(_){}
 if(!['light','dark'].includes(stored))stored=null;
 document.documentElement.dataset.theme=stored||'dark';
 function label(){const button=document.getElementById('themeToggle');if(!button)return;const light=document.documentElement.dataset.theme==='light';button.textContent=light?'🌙 다크 모드':'☀️ 라이트 모드';button.setAttribute('aria-label',light?'다크 모드로 전환':'라이트 모드로 전환');button.setAttribute('aria-pressed',String(light))}
 function apply(theme){const changed=document.documentElement.dataset.theme!==theme;document.documentElement.dataset.theme=theme;label();if(changed)window.dispatchEvent(new CustomEvent('er-theme-change',{detail:{theme}}))}
 window.applyThemeForRole=role=>apply(stored||(role==='admin'?'dark':'light'));
 document.addEventListener('DOMContentLoaded',()=>{
  const button=document.getElementById('themeToggle');if(!button)return;
  button.addEventListener('click',()=>{stored=document.documentElement.dataset.theme==='light'?'dark':'light';try{localStorage.setItem('er_theme',stored)}catch(_){}apply(stored)});label();
 });
})();
