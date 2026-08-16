const form = document.querySelector('#scan-form');
const result = document.querySelector('#result');
const submit = document.querySelector('#submit');
const network = document.querySelector('#network');
const issuer = document.querySelector('#issuer');

const issuers = {
  mainnet: 'GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN',
  testnet: 'GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5',
};

network.addEventListener('change', () => { issuer.value = issuers[network.value]; });

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  submit.disabled = true;
  submit.querySelector('span').textContent = 'READING HORIZON EVIDENCE…';
  try {
    const response = await fetch('/api/scan', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        network: network.value,
        asset_code: document.querySelector('#asset-code').value,
        issuer: issuer.value,
        max_holders: 200,
      }),
    });
    const report = await response.json();
    render(report);
  } catch (error) {
    render({verdict: 'INSUFFICIENT_DATA', risk_score: null, evidence_quality: 'UNAVAILABLE', signals: [], limitations: [String(error)]});
  } finally {
    submit.disabled = false;
    submit.querySelector('span').textContent = 'RUN EVIDENCE SCAN';
  }
});

function render(report) {
  result.hidden = false;
  const verdict = report.verdict || 'INSUFFICIENT_DATA';
  result.dataset.verdict = verdict;
  const verdictEl = document.querySelector('#verdict');
  verdictEl.textContent = verdict.replaceAll('_', ' ');
  verdictEl.className = verdict.toLowerCase().replaceAll('_', '-');
  document.querySelector('#score').textContent = report.risk_score ?? '—';
  document.querySelector('#quality').textContent = `Evidence quality: ${report.evidence_quality || 'UNKNOWN'}${report.latest_ledger ? ` · Ledger ${report.latest_ledger}` : ''}`;
  const signals = document.querySelector('#signals');
  signals.replaceChildren();
  for (const item of report.signals || []) {
    const node = document.createElement('article');
    node.className = 'signal';
    const title = document.createElement('strong');
    title.textContent = item.code;
    const points = document.createElement('span');
    points.className = 'points';
    points.textContent = `${item.risk_points > 0 ? '+' : ''}${item.risk_points}`;
    title.append(points);
    const summary = document.createElement('p');
    summary.textContent = item.summary;
    node.append(title, summary);
    signals.append(node);
  }
  for (const limitation of report.limitations || []) {
    const node = document.createElement('article');
    node.className = 'signal';
    node.innerHTML = '<strong>limitation</strong>';
    const text = document.createElement('p');
    text.textContent = limitation;
    node.append(text);
    signals.append(node);
  }
  document.querySelector('#raw').textContent = JSON.stringify(report, null, 2);
  result.scrollIntoView({behavior: 'smooth', block: 'start'});
}
