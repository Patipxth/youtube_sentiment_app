// อ้างอิง element
const mainForm = document.getElementById('mainForm');
const urlInput = document.getElementById('url_input');
const submitButton = document.getElementById('submitButton');
const analysisModeHidden = document.getElementById('analysisModeHidden');
const loadingOverlay = document.getElementById('loadingOverlay');

const inputTypeRadios = document.querySelectorAll('input[name="input_type"]');
const errorMessageDiv = document.getElementById('errorMessage');

// helper: toggle overlay
function setLoading(on){
  if(!loadingOverlay) return;
  loadingOverlay.classList.toggle('show', !!on);
}

// อัปเดตฟอร์มตามประเภท
function updateForm(){
  const selected = document.querySelector('input[name="input_type"]:checked').value;
  analysisModeHidden.value = selected;

  if(selected === 'video'){
    urlInput.placeholder = 'กรอกลิงก์วิดีโอ เช่น https://www.youtube.com/watch?v=xxxxxxxxxxx';
    submitButton.value = 'วิเคราะห์ความคิดเห็น';
  }else{
    urlInput.placeholder = 'กรอกลิงก์ช่อง เช่น https://youtube.com/@ชื่อช่อง';
    submitButton.value = 'แสดงวิดีโอในช่อง';
  }

  // ปรับ aria-selected ให้ label ของ segmented
  document.querySelectorAll('.segmented-selector input').forEach(inp=>{
    const lbl = inp.nextElementSibling;
    if(lbl) lbl.setAttribute('aria-selected', inp.checked ? 'true' : 'false');
  });
}

// bind change
inputTypeRadios.forEach(r => r.addEventListener('change', updateForm));
updateForm();

// submit
mainForm.addEventListener('submit', () => {
  // ซ่อน error เก่า
  if(errorMessageDiv){
    errorMessageDiv.style.display = 'none';
    errorMessageDiv.textContent = '';
  }
  // โชว์ overlay + disable ปุ่ม
  setLoading(true);
  submitButton.disabled = true;
});
