import json 
from app.models import LogicProgram 
from app.structured_extractor import StructuredExtractorRuntime 
data = json.load(open('data/case_009_response.json','r',encoding='utf-8')) 
program = LogicProgram(**data['logic_program']) 
ser = StructuredExtractorRuntime(llm_client=None) 
ser._hydrate_predicates(program) 
print(sorted(program.predicates.keys()))
