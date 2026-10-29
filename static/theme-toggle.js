'use strict';
(function(){
 let stored='dark';try{stored=localStorage.getItem('er_theme')||'dark'}catch(_){}
 document.documentElement.dataset.theme=stored==='light'?'light':'dark';
 document.addEventListener('DOMContentLoaded',()=>{
  const button=document.getElementById('themeToggle');if(!button)return;
  function label(){const light=document.documentElement.dataset.theme==='light';button.textContent=light?'🌙 다크 모드':'☀️ 라이트 모드';button.setAttribute('aria-label',light?'다크 모드로 전환':'라이트 모드로 전환');button.setAttribute('aria-pressed',String(light))}
  button.addEventListener('click',()=>{const next=document.documentElement.dataset.theme==='light'?'dark':'light';document.documentElement.dataset.theme=next;try{localStorage.setItem('er_theme',next)}catch(_){}label();window.dispatchEvent(new CustomEvent('er-theme-change',{detail:{theme:next}}))});label();
 });
})();
