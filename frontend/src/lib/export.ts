/**
 * Table export. CSV is built from the table as shown. PDF uses the browser's print-to-PDF with the same A4 layout as
 * the FDR evidence packet (no PDF library is bundled): the table is copied into the print root, printed, then removed.
 */

const clean = (s: string) => s.replace(/\s+/g, ' ').trim();

function cellText(c: HTMLTableCellElement) {
  const copy = c.cloneNode(true) as HTMLElement;
  copy.querySelectorAll('.sr-only, button, [data-no-export]').forEach((n) => n.remove());
  return clean(copy.textContent ?? '');
}

export function tableRows(table: HTMLTableElement): string[][] {
  return Array.from(table.rows)
    .filter((r) => !r.querySelector('.empty'))
    .map((r) => Array.from(r.cells).map(cellText))
    .map((cells, i, all) => (i === 0 ? cells : cells.slice(0, all[0].length)))
    .filter((cells) => cells.some(Boolean));
}

const csvCell = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);

export function downloadCsv(name: string, rows: string[][], note?: string) {
  const lines = [...(note ? [`# ${note}`] : []), ...rows.map((r) => r.map(csvCell).join(','))];
  const blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${name}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

export const fileSlug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '').slice(0, 60) || 'table';

/** Prints `node` alone, inside the packet page frame (header, generated-at line, SIMULATED note, footer). */
export function printNode(node: HTMLElement, opts: { title: string; simulated?: boolean; subtitle?: string }) {
  const root = document.createElement('div');
  root.className = 'print-root';
  const now = new Date();
  root.innerHTML = `
    <header class="pk-head">
      <div><b>All India Council for Technical Education</b><span>NIDHIVEDA · Security Deposit &amp; FDR Management Portal</span></div>
      <div class="pk-meta"><span>Generated ${now.toLocaleString('en-IN')}</span>${opts.simulated ? '<span class="pk-sim">SIMULATED bank data</span>' : ''}</div>
    </header>
    <h1 class="pk-title"></h1>
    ${opts.subtitle ? '<p class="pk-sub"></p>' : ''}
    <div class="pk-body"></div>
    <footer class="pk-foot">Printed from NIDHIVEDA. Bank channels in this build are simulated; this document is not an AICTE record.</footer>`;
  (root.querySelector('.pk-title') as HTMLElement).textContent = opts.title;
  if (opts.subtitle) (root.querySelector('.pk-sub') as HTMLElement).textContent = opts.subtitle;
  const copy = node.cloneNode(true) as HTMLElement;
  copy.querySelectorAll('button, .chart-tools, .table-tools, [data-no-print]').forEach((n) => n.remove());
  copy.removeAttribute('style');
  root.querySelector('.pk-body')!.appendChild(copy);
  document.body.appendChild(root);
  document.body.classList.add('printing-node');
  const done = () => {
    document.body.classList.remove('printing-node');
    root.remove();
    window.removeEventListener('afterprint', done);
  };
  window.addEventListener('afterprint', done);
  window.print();
  // some browsers do not fire afterprint when the dialog is dismissed quickly
  setTimeout(() => document.body.contains(root) && !matchMedia('print').matches && done(), 1500);
}
