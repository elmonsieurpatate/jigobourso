(async () => { if (!await J.init('explorer')) return; await AdminColumns.render(J.$('#page'), { mine: true }); })();
