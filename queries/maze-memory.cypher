MATCH (s:SleepRun {id:$artifact,status:'complete'})-[:GENERATED]->(p:ProcedureVersion)-[:BASED_ON]->(h:Hypothesis)-[:SUPPORTED_BY]->(o:Observation)
RETURN p.id, p.title, h.id, h.description, o.id, o.payload
