# Human-review notifications.
#
# When the workflow decides a document needs a person, Step Functions publishes
# to this SNS topic. If you provide reviewer_email, an email subscription is
# created (you must click the confirmation link AWS emails you once).

resource "aws_sns_topic" "review" {
  name = "${local.name_prefix}-review"
}

# Only create the email subscription if an address was supplied.
resource "aws_sns_topic_subscription" "email" {
  count     = var.reviewer_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.review.arn
  protocol  = "email"
  endpoint  = var.reviewer_email
}
