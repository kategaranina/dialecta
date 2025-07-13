from collections import Counter
import sqlite3


conn = sqlite3.connect('../db.sqlite3')
c = conn.cursor()

recs = c.execute("""
    SELECT data, id 
    FROM corpora_recording 
""").fetchall()

counts = Counter([x[0] for x in recs])
dupl = [rec for rec, count in counts.items() if count > 1]

for d in dupl:
    dupl_ids = [i[1] for i in recs if d == i[0]]

    if len(dupl_ids) > 1:
        print(d, dupl_ids)
        to_remove = dupl_ids[1:]
        for r_id in to_remove:
            q = "DELETE from corpora_recording where id = " + str(r_id)
            c.execute(q)

conn.commit()
c.close()
