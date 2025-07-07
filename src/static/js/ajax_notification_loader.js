
<script>
function showToast(message) {
  const container = document.getElementById('toast-container') || (() => {
    const div = document.createElement('div');
    div.id = 'toast-container';
    div.style.position = 'fixed';
    div.style.top = '20px';
    div.style.left = '50%';
    div.style.transform = 'translateX(-50%)';
    div.style.zIndex = '9999';
    document.body.appendChild(div);
    return div;
  })();

  const toast = document.createElement('div');
  toast.innerText = message;
  toast.style.backgroundColor = '#007bff';
  toast.style.color = '#fff';
  toast.style.padding = '12px 20px';
  toast.style.marginBottom = '10px';
  toast.style.borderRadius = '8px';
  toast.style.boxShadow = '0 0 10px rgba(0,0,0,0.3)';
  toast.style.opacity = '0.95';
  toast.style.transition = 'opacity 0.5s ease';

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 500);
  }, 4000);
}

// جلب الإشعارات كل 15 ثانية
setInterval(() => {
  fetch('/api/notifications/unread')
    .then(res => res.json())
    .then(data => {
      data.forEach(n => {
        showToast(n.content);
      });
    });
}, 15000);
</script>
