MATCH (r:IncidentRun {id:$run})-[:OBSERVED]->(before:IncidentObservation)-[:NEXT]->(after:IncidentObservation)
RETURN r.id, before.id, before.payload, after.id, after.payload
