data "aws_iam_policy_document" "ecs_tasks_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task_execution" {
  name               = "${local.name}-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume_role.json
}

data "aws_iam_policy_document" "task_execution" {
  statement {
    sid       = "GetECRAuthorizationToken"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "PullApplicationImage"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [aws_ecr_repository.app.arn]
  }

  statement {
    sid    = "WriteApplicationLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.app.arn}:*"]
  }

  statement {
    sid     = "ReadApplicationConnectionSecrets"
    effect  = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      aws_secretsmanager_secret.database_url.arn,
      aws_secretsmanager_secret.redis_url.arn,
    ]
  }

  dynamic "statement" {
    for_each = var.secrets_kms_key_arn == null ? [] : [var.secrets_kms_key_arn]

    content {
      sid       = "DecryptApplicationSecrets"
      effect    = "Allow"
      actions   = ["kms:Decrypt"]
      resources = [statement.value]
    }
  }
}

resource "aws_iam_role_policy" "task_execution" {
  name   = "${local.name}-task-execution"
  role   = aws_iam_role.task_execution.id
  policy = data.aws_iam_policy_document.task_execution.json
}

resource "aws_iam_role" "task" {
  name               = "${local.name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume_role.json
}

data "aws_iam_policy_document" "task" {
  statement {
    sid    = "ManageUploadObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = ["${aws_s3_bucket.uploads.arn}/uploads/*"]
  }
}

resource "aws_iam_role_policy" "task" {
  name   = "${local.name}-task"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task.json
}
