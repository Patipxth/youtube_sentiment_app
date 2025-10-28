const overlay   = document.getElementById('loadingOverlay');
const grid      = document.getElementById('allVideosGrid');
const loadBtn   = document.getElementById('loadMoreButton');
const container = document.getElementById('allVideosContainer');

function setLoading(on){ if(!overlay) return; overlay.classList.toggle('show', !!on); }
function escapeHtml(s=''){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}

// NEW: normalize token ที่อาจเป็น "None"/"null"/ช่องว่าง
function normToken(t){
  const v = (t ?? '').toString().trim().toLowerCase();
  return (v === '' || v === 'none' || v === 'null' || v === 'undefined') ? '' : (t+'');
}

// ซ่อนปุ่มถ้าไม่มีโทเคนตั้งแต่โหลดครั้งแรก
if (loadBtn && container && !normToken(container.dataset.nextPageToken)) {
  loadBtn.style.display = 'none';
}

// จับ submit ฟอร์ม
document.addEventListener('submit', (ev)=>{
  const form = ev.target.closest('.analyze-form');
  if(!form) return;
  setLoading(true);
  document.querySelectorAll('.analyze-button').forEach(b=>b.disabled=true);
}, true);

function createVideoItemHtml(video){
  const chId  = container?.dataset.channelId || '';
  const chUrl = container?.dataset.channelUrl || '';
  const title = escapeHtml(video.title);
  const url   = escapeHtml(video.video_url);
  const thumb = escapeHtml(video.thumbnail);
  const type  = escapeHtml(video.video_type);
  return `
    <article class="video-item">
      <a href="${url}" target="_blank" class="thumb-wrap" aria-label="${title}">
        <img src="${thumb}" alt="ปกคลิป" class="thumb">
      </a>
      <div class="video-body">
        <h3 class="video-title" title="${title}">${title}</h3>
        <span class="video-type">${type}</span>
      </div>
      <form class="analyze-form" action="/analyze" method="post">
        <input type="hidden" name="input_url" value="${url}">
        <input type="hidden" name="analysis_mode" value="video">
        <input type="hidden" name="channel_id" value="${chId}">
        <input type="hidden" name="channel_url" value="${chUrl}">
        <button type="submit" class="analyze-button">วิเคราะห์ความคิดเห็น</button>
      </form>
    </article>
  `;
}

// Load More
if (loadBtn && grid && container) {
  loadBtn.addEventListener('click', async ()=>{
    const channelId    = container.dataset.channelId;
    const nextPageToken = normToken(container.dataset.nextPageToken);

    if (!nextPageToken) { loadBtn.style.display = 'none'; return; }

    loadBtn.disabled = true;
    loadBtn.textContent = 'กำลังโหลด...';
    setLoading(true);

    try{
      const url = `/load_more_channel_videos?channel_id=${encodeURIComponent(channelId)}&page_token=${encodeURIComponent(nextPageToken)}`;
      const res = await fetch(url);
      if(!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      const items = Array.isArray(data.all_videos) ? data.all_videos : [];
      const newToken = normToken(data.next_page_token);

      if(items.length){
        const frag = document.createDocumentFragment();
        for(const v of items){
          const wrap = document.createElement('div');
          wrap.innerHTML = createVideoItemHtml(v).trim();
          frag.appendChild(wrap.firstElementChild);
        }
        grid.appendChild(frag);
      }

      container.dataset.nextPageToken = newToken;
      loadBtn.style.display = newToken ? 'block' : 'none';
    }catch(err){
      console.error('Error loading more videos:', err);
      alert('เกิดข้อผิดพลาดในการโหลดวิดีโอเพิ่มเติม: ' + err.message);
      loadBtn.style.display = 'none';
    }finally{
      loadBtn.disabled = false;
      loadBtn.textContent = 'ดูเพิ่มเติม';
      setLoading(false);
    }
  });
}
