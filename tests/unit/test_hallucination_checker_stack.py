import aws_cdk as core
import aws_cdk.assertions as assertions

from hallucination_checker.hallucination_checker_stack import HallucinationCheckerStack

# example tests. To run these tests, uncomment this file along with the example
# resource in hallucination_checker/hallucination_checker_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = HallucinationCheckerStack(app, "hallucination-checker")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
