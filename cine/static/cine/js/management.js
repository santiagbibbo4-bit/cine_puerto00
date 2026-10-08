(function () {
  'use strict';

  var button = document.getElementById('add-screening');
  var template = document.getElementById('screening-empty-form');
  var list = document.getElementById('screening-forms');
  var total = document.getElementById('id_screenings-TOTAL_FORMS');
  if (!button || !template || !list || !total) return;

  button.addEventListener('click', function () {
    var index = Number(total.value);
    var markup = template.innerHTML.replace(/__prefix__/g, String(index));
    var wrapper = document.createElement('div');
    wrapper.innerHTML = markup.trim();
    list.appendChild(wrapper.firstElementChild);
    total.value = String(index + 1);
  });
})();
