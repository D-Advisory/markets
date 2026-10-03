<?php
/*
 * D-Advisory: one-time helper that adds "Markets & Economy" to the Resources menu
 * on every page of dinian.ca.
 *
 *   1. Open https://dinian.ca/add-markets-menu.php        -> preview (changes nothing)
 *   2. Click "Add the menu link"                           -> backs up and updates the pages,
 *                                                             then deletes this file.
 *
 * Backups go to public_html/dadv-backup-YYYYMMDD-HHMMSS/ (same folder structure).
 * Running it twice is safe: pages that already have the link are skipped.
 */
header('Content-Type: text/html; charset=utf-8');
header('X-Robots-Tag: noindex');

$root   = __DIR__;
$anchor = '<li class="menu-item menu-item-type-custom menu-item-object-custom" id="menu-item-673">';
$marker = 'id="menu-item-9001"';
$newLi  = '<li class="menu-item menu-item-type-custom menu-item-object-custom" id="menu-item-9001"><a href="/markets-economy/"><span class="eb_menu_title">Markets &amp; Economy</span></a></li>' . "\n";
$apply  = isset($_POST['apply']) && $_POST['apply'] === 'yes';

$skipDirs = array('wp-content', 'wp-includes', 'cgi-bin', '.well-known');
$todo = array(); $done = array(); $skipped = array(); $errors = array();

$it = new RecursiveIteratorIterator(
    new RecursiveCallbackFilterIterator(
        new RecursiveDirectoryIterator($root, FilesystemIterator::SKIP_DOTS),
        function ($f) use ($skipDirs) {
            $n = $f->getFilename();
            if ($f->isDir()) return !in_array($n, $skipDirs, true) && strpos($n, 'dadv-backup-') !== 0;
            return preg_match('/\.html?$/i', $n) === 1;
        }
    )
);
foreach ($it as $f) {
    $path = $f->getPathname();
    $rel  = ltrim(substr($path, strlen($root)), '/');
    $html = @file_get_contents($path);
    if ($html === false) { $errors[] = "$rel (could not read)"; continue; }
    if (strpos($html, $anchor) === false) continue;           // not a D-Advisory page
    if (strpos($html, $marker) !== false) { $skipped[] = $rel; continue; } // already has the link
    if (substr_count($html, $anchor) !== 1) { $errors[] = "$rel (menu found more than once, left alone)"; continue; }
    $todo[$rel] = $html;
}
ksort($todo);

if ($apply && $todo) {
    $backup = $root . '/dadv-backup-' . date('Ymd-His');
    foreach ($todo as $rel => $html) {
        $dest = $backup . '/' . $rel;
        if (!is_dir(dirname($dest)) && !@mkdir(dirname($dest), 0755, true)) { $errors[] = "$rel (could not create backup folder)"; continue; }
        if (!@copy($root . '/' . $rel, $dest)) { $errors[] = "$rel (backup failed, page left alone)"; continue; }
        $new = str_replace($anchor, $newLi . $anchor, $html);
        if (@file_put_contents($root . '/' . $rel, $new, LOCK_EX) === false) { $errors[] = "$rel (could not save)"; continue; }
        $done[] = $rel;
    }
    if (!$errors) { @unlink(__FILE__); }
}

function li($items) { $o = ''; foreach ($items as $i) $o .= '<li>' . htmlspecialchars($i) . '</li>'; return $o; }
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Add Markets &amp; Economy to the menu</title>
<style>
body{font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:760px;margin:40px auto;padding:0 16px;color:#1d2a33;background:#fff}
h1{color:#0A3D5A;font-size:26px}.ok{color:#11744a}.err{color:#b3261e}
button{background:#CC6600;color:#fff;border:0;border-radius:6px;padding:12px 22px;font-size:16px;cursor:pointer}
ul{columns:2;font-size:14px}
</style></head><body>
<h1>Add “Markets &amp; Economy” to the Resources menu</h1>
<?php if ($apply): ?>
  <?php if ($done): ?><p class="ok"><strong>Done.</strong> Updated <?= count($done) ?> page(s). Backups are in <code><?= htmlspecialchars(basename($backup)) ?></code>.</p><ul><?= li($done) ?></ul><?php endif; ?>
  <?php if (!$todo): ?><p class="ok">Nothing to do: every page already has the link.</p><?php endif; ?>
  <?php if ($errors): ?><p class="err"><strong>Some pages were not changed:</strong></p><ul><?= li($errors) ?></ul><p>This helper file was kept so you can try again. Send a screenshot of this page to Claude.</p>
  <?php else: ?><p>This helper file has deleted itself. If your site uses a firewall cache, clear it so visitors see the new menu right away.</p><?php endif; ?>
<?php else: ?>
  <p>This adds a <strong>Markets &amp; Economy</strong> link under <strong>Resources</strong> on each page below. Nothing has changed yet.</p>
  <?php if ($todo): ?>
    <p><strong><?= count($todo) ?> page(s) will be updated:</strong></p><ul><?= li(array_keys($todo)) ?></ul>
    <?php if ($skipped): ?><p><?= count($skipped) ?> page(s) already have the link and will be skipped.</p><?php endif; ?>
    <form method="post"><input type="hidden" name="apply" value="yes"><button type="submit">Add the menu link</button></form>
  <?php else: ?><p class="ok">Nothing to do: <?= $skipped ? 'every page already has the link.' : 'no D-Advisory menu was found. Make sure this file is in the public_html folder.' ?></p><?php endif; ?>
  <?php if ($errors): ?><p class="err">Will be left alone:</p><ul><?= li($errors) ?></ul><?php endif; ?>
<?php endif; ?>
</body></html>
