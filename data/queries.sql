-- Builds a CSV like the original one, with sol_id and message in the link field
\copy (  select solution_id "Solution Id", username "Username", category "Level Category", number "Level Number", name "Level Name", 
                reactor_count "Reactor Count", cycle_count "Cycle Count", symbol_count "Symbol Count", 
                upload_time "Upload Time", youtube "Youtube Link", description "Comment" 
           from solutions natural join users natural join levels
       order by category, order1, order2, reactor_count, cycle_count, symbol_count, upload_time)
to 'score_dump2.csv'
with csv delimiter ',' header;

-- Gets seeds (SQLite only)
select c.type, p.output_id, p.x, p.y
from component c, pipe p
where c.rowid = p.component_id
group by c.type, output_id
having min(p.rowid)
order by c.type
