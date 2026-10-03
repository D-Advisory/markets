<?php
/*
 * D-Advisory: one-time UNDO for the "Markets & Economy" menu link on dinian.ca.
 *
 *   1. Open https://dinian.ca/undo-markets-menu.php   -> preview (changes nothing)
 *   2. Click "Undo"                                    -> puts the original pages back from
 *                                                        the dadv-backup-... folder, optionally
 *                                                        removes the Markets & Economy page,
 *                                                        then deletes this file.
 *
 * Only pages that still contain the added link are restored, so it is safe to run twice.
 */
header('Content-Type: text/html; charset=utf-8');
header('X-Robots-Tag: noindex');

$root   = __DIR__;
$marker = 'id="menu-item-9001"';
$apply  = isset($_POST['apply']) && $_POST['apply'] === 'yes';
$removePage = $apply ? !empty($_POST['remove_page']) : true;

// Use the most recent backup folder made by the add-menu helper.
$backups = glob($root . '/dadv-backup-*', GLOB_ONLYDIR);
sort($backups);
$backup = $backups ? end($backups) : null;

$todo = array(); $done = array(); $errors = array(); $notInBackup = array();
if ($backup) {
    $it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($backup, FilesystemIterator::SKIP_DOTS));
    foreach ($it as $f) {
        if (!preg_match('/\.html?$/i', $f->getFilename())) continue;
        $rel  = ltrim(substr($f->getPathname(), strlen($backup)), '/');
        $live = $root . '/' . $rel;
        $orig = @file_get_contents($f->getPathname());
        if ($orig === false || strpos($orig, $marker) !== false) { $errors[] = "$rel (backup copy unreadable or not an original)"; continue; }
        $cur = @file_get_contents($live);
        if ($cur !== false && strpos($cur, $marker) === false) continue; // already back to normal
        $todo[$rel] = $f->getPathname();
    }
    ksort($todo);
}
$pageDir = $root . '/markets-economy';
$pageExists = is_file($pageDir . '/index.html');

$pageRemoved = false;
if ($apply) {
    foreach ($todo as $rel => $src) {
        $live = $root . '/' . $rel;
        if (!is_dir(dirname($live)) && !@mkdir(dirname($live), 0755, true)) { $errors[] = "$rel (could not create folder)"; continue; }
        if (!@copy($src, $live)) { $errors[] = "$rel (could not restore)"; continue; }
        $done[] = $rel;
    }
    if ($removePage && $pageExists) {
        $ok = @unlink($pageDir . '/index.html');
        if ($ok) { @rmdir($pageDir); $pageRemoved = true; }
        else { $errors[] = 'markets-economy/index.html (could not delete the page)'; }
    }
    if (!$errors) { @unlink(__FILE__); }
}

function li($items) { $o = ''; foreach ($items as $i) $o .= '<li>' . htmlspecialchars($i) . '</li>'; return $o; }
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Undo the Markets &amp; Economy menu link</title>
<style>
body{font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:760px;margin:40px auto;padding:0 16px;color:#1d2a33;background:#fff}
h1{color:#0A3D5A;font-size:26px}.ok{color:#11744a}.err{color:#b3261e}
button{background:#0A3D5A;color:#fff;border:0;border-radius:6px;padding:12px 22px;font-size:16px;cursor:pointer}
label{display:block;margin:16px 0}
ul{columns:2;font-size:14px}
</style></head><body>
<h1>Undo: remove “Markets &amp; Economy” from the menu</h1>
<?php if (!$backup): ?>
  <p class="err">No backup folder (dadv-backup-…) was found in public_html, so there is nothing to restore from. Nothing was changed. Send a screenshot of this page to Claude.</p>
<?php elseif ($apply): ?>
  <?php if ($done): ?><p class="ok"><strong>Done.</strong> Restored <?= count($done) ?> original page(s) from <code><?= htmlspecialchars(basename($backup)) ?></code>.</p><ul><?= li($done) ?></ul><?php endif; ?>
  <?php if (!$todo): ?><p class="ok">The menu was already back to the original on every page.</p><?php endif; ?>
  <?php if ($pageRemoved): ?><p class="ok">The Markets &amp; Economy page has been removed.</p><?php endif; ?>
  <?php if ($errors): ?><p class="err"><strong>Some items were not changed:</strong></p><ul><?= li($errors) ?></ul><p>This undo file was kept so you can try again. Send a screenshot of this page to Claude.</p>
  <?php else: ?><p>This undo file has deleted itself. You can now delete the <code><?= htmlspecialchars(basename($backup)) ?></code> folder in File Manager. If a page still shows the link, the firewall is showing an older saved copy; it clears within a few hours.</p><?php endif; ?>
<?php else: ?>
  <p>This puts back the original version of each page below, from <code><?= htmlspecialchars(basename($backup)) ?></code>, so the <strong>Markets &amp; Economy</strong> link disappears from the menu. Nothing has changed yet.</p>
  <?php if ($todo): ?>
    <p><strong><?= count($todo) ?> page(s) will be restored:</strong></p><ul><?= li(array_keys($todo)) ?></ul>
  <?php else: ?><p class="ok">The menu is already back to the original on every page.</p><?php endif; ?>
  <?php if ($errors): ?><p class="err">Will be left alone:</p><ul><?= li($errors) ?></ul><?php endif; ?>
  <?php if ($todo || $pageExists): ?>
  <form method="post"><input type="hidden" name="apply" value="yes">
    <?php if ($pageExists): ?><label><input type="checkbox" name="remove_page" value="1" checked> Also remove the Markets &amp; Economy page (dinian.ca/markets-economy/)</label><?php endif; ?>
    <button type="submit">Undo</button>
  </form>
  <?php endif; ?>
<?php endif; ?>
</body></html>
