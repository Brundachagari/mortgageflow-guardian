# Values printed after `terraform apply` -- the handles you need to use or demo
# the system (upload target, where to look for results, etc.).

output "documents_bucket" {
  description = "Upload fictional documents under the incoming/ prefix here."
  value       = aws_s3_bucket.documents.bucket
}

output "processing_queue_url" {
  description = "The SQS processing queue."
  value       = aws_sqs_queue.processing.url
}

output "dead_letter_queue_url" {
  description = "Where permanently-failed documents are preserved."
  value       = aws_sqs_queue.dlq.url
}

output "documents_table" {
  description = "DynamoDB table holding standardized document records."
  value       = aws_dynamodb_table.documents.name
}

output "state_machine_arn" {
  description = "The Step Functions workflow."
  value       = aws_sfn_state_machine.pipeline.arn
}

output "review_topic_arn" {
  description = "SNS topic for human-review alerts."
  value       = aws_sns_topic.review.arn
}

output "dashboard_name" {
  description = "CloudWatch dashboard with the system overview."
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}
