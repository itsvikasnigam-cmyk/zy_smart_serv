/// Minimal line-based diff for SOP Markdown (LCS on lines; typical sizes are small).

enum DiffLineKind { same, removed, added }

class DiffLine {
  const DiffLine(this.kind, this.text);
  final DiffLineKind kind;
  final String text;
}

List<DiffLine> unifiedLineDiff(String a, String b) {
  final la = a.split('\n');
  final lb = b.split('\n');
  final n = la.length;
  final m = lb.length;
  final dp = List.generate(
    n + 1,
    (_) => List<int>.filled(m + 1, 0),
  );
  for (var i = n - 1; i >= 0; i--) {
    for (var j = m - 1; j >= 0; j--) {
      if (la[i] == lb[j]) {
        dp[i][j] = 1 + dp[i + 1][j + 1];
      } else {
        final down = dp[i + 1][j];
        final right = dp[i][j + 1];
        dp[i][j] = down > right ? down : right;
      }
    }
  }
  var i = 0;
  var j = 0;
  final out = <DiffLine>[];
  while (i < n && j < m) {
    if (la[i] == lb[j]) {
      out.add(DiffLine(DiffLineKind.same, la[i]));
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.add(DiffLine(DiffLineKind.removed, la[i]));
      i++;
    } else {
      out.add(DiffLine(DiffLineKind.added, lb[j]));
      j++;
    }
  }
  while (i < n) {
    out.add(DiffLine(DiffLineKind.removed, la[i]));
    i++;
  }
  while (j < m) {
    out.add(DiffLine(DiffLineKind.added, lb[j]));
    j++;
  }
  return out;
}
