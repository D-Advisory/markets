/* Shows ID-Advisory branding (instead of D-Advisory / dinian.ca) when this dashboard
   is displayed on idadvisory.ca. On dinian.ca nothing changes. */
(function () {
  var host = '';
  try { host = new URL(document.referrer).hostname; } catch (e) {}
  var isID = /idadvisory/i.test(host) || /[?&]brand=id\b/i.test(location.search);
  if (!isID) return;

  function fixText(s) {
    return s
      .replace(/(^|[^I])D-Advisory Group/g, '$1ID-Advisory')
      .replace(/(^|[^I])D-Advisory/g, '$1ID-Advisory')
      .replace(/(^|[^I])D-ADVISORY/g, '$1ID-ADVISORY')
      .replace(/dinian\.ca/g, 'idadvisory.ca');
  }
  function run() {
    if (!document.body) return;
    var w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null), n, list = [];
    while ((n = w.nextNode())) {
      if (/D-Advisory|D-ADVISORY|dinian\.ca/.test(n.nodeValue)) list.push(n);
    }
    list.forEach(function (t) { t.nodeValue = fixText(t.nodeValue); });
    document.querySelectorAll('a[href*="dinian.ca"]').forEach(function (a) {
      a.href = a.href.replace(/https?:\/\/(www\.)?dinian\.ca/, 'https://idadvisory.ca');
    });
    document.title = fixText(document.title);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run); else run();
  window.addEventListener('load', run);
  setTimeout(run, 1500);
  setTimeout(run, 4000);
})();
