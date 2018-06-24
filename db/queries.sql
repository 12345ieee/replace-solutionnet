-- Builds a CSV like the original one, with sol_id and message in the link field
\copy (  select solution_id "Solution Id", username "Username", category "Level Category", number "Level Number", name "Level Name", 
                reactor_count "Reactor Count", cycle_count "Cycle Count", symbol_count "Symbol Count", 
                upload_time "Upload Time", youtube "Youtube Link", description "Comment" 
           from solutions natural join users natural join levels
       order by category, order1, order2, reactor_count, cycle_count, symbol_count, upload_time)
to 'score_dump2.csv'
with csv delimiter ',' header;
