(()=>{'use strict';
const form=document.querySelector('[data-search]');
if(form){const input=form.querySelector('input'),rows=[...document.querySelectorAll('[data-case]')],status=document.querySelector('[data-results]'),empty=document.querySelector('[data-no-results]');
const run=()=>{const query=input.value.trim().normalize('NFKC').toLocaleLowerCase(),terms=query.split(/\s+/).filter(Boolean);let count=0;for(const row of rows){const ok=terms.every(term=>(row.dataset.search||row.textContent).normalize('NFKC').toLocaleLowerCase().includes(term));row.hidden=!ok;if(ok)count++}if(status)status.textContent=query?`“${input.value.trim()}” 검색 결과 ${count}건`:`현재 목록 ${count}건`;if(empty)empty.hidden=count!==0;};
form.addEventListener('submit',e=>{e.preventDefault();run()});input.addEventListener('input',run);const query=new URLSearchParams(location.search).get('q');if(query){input.value=query;run();}}
for(const button of document.querySelectorAll('[data-print]'))button.addEventListener('click',()=>window.print());
})();
