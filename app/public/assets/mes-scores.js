(async () => { if (!await J.init('explorer')) return; await AdminScores.render(J.$('#page'), { mine: true }); })();
