(function(){
  // Menú móvil
  var h=document.querySelector('header'), b=h&&h.querySelector('.abrir');
  if(b){var abrir=b.getAttribute('aria-label'), cerrar=b.getAttribute('data-cerrar')||abrir;
    b.addEventListener('click',function(){var o=h.classList.toggle('abierto');b.setAttribute('aria-expanded',o);b.setAttribute('aria-label',o?cerrar:abrir);});}

  // Formularios de alta (Make → Mailchimp)
  // Antispam: campo trampa + los envíos en menos de 2,5 s se dan por buenos sin enviarse (bots)
  var t0=Date.now();
  document.querySelectorAll('form.alta').forEach(function(f){
    var m=f.querySelector('.mensaje'), btn=f.querySelector('button'), d=f.dataset;
    f.addEventListener('submit',function(e){
      e.preventDefault();
      var email=f.Email.value.trim();
      if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){m.textContent=d.mEmail;f.Email.focus();return;}
      if(!f.Newsletter.checked){m.textContent=d.mPriv;return;}
      if(f.website.value||Date.now()-t0<2500){f.reset();m.textContent=d.mOk;return;}
      btn.disabled=true;m.textContent=d.mEnv;
      fetch(d.hook,{method:'POST',mode:'no-cors',body:new URLSearchParams({Email:email,Idioma:d.idioma,Newsletter:'on'})})
        .then(function(){f.reset();m.textContent=d.mOk;})
        .catch(function(){m.textContent=d.mErr;})
        .finally(function(){btn.disabled=false;});
    });
  });

})();
