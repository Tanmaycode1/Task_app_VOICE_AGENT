"""Seed the database with mock tasks."""

from datetime import datetime, timedelta

from app.db.base import SessionLocal
from app.models.task import Task, TaskPriority, TaskStatus


def seed_tasks():
    """Add mock tasks to the database."""
    db = SessionLocal()
    
    # Clear existing tasks
    db.query(Task).delete()
    
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    mock_tasks = [
        # Today's tasks with specific hours
        Task(
            title="Morning standup meeting",
            description="Daily team sync",
            priority=TaskPriority.HIGH.value,
            status=TaskStatus.COMPLETED.value,
            deadline=today + timedelta(hours=9),
            completed_at=today + timedelta(hours=9, minutes=15),
            created_at=today - timedelta(days=1),
        ),
        Task(
            title="Review pull requests",
            description="Code review for authentication module",
            priority=TaskPriority.MEDIUM.value,
            status=TaskStatus.IN_PROGRESS.value,
            deadline=today + timedelta(hours=11),
            created_at=today - timedelta(days=1),
        ),
        Task(
            title="Lunch with client",
            description="Discuss Q4 requirements",
            priority=TaskPriority.HIGH.value,
            status=TaskStatus.TODO.value,
            deadline=today + timedelta(hours=13),
            created_at=today,
        ),
        Task(
            title="Backend API development",
            description="Implement task filtering endpoints",
            priority=TaskPriority.URGENT.value,
            status=TaskStatus.IN_PROGRESS.value,
            deadline=today + timedelta(hours=16),
            created_at=today,
        ),
        Task(
            title="Update documentation",
            description="API docs for new endpoints",
            priority=TaskPriority.LOW.value,
            status=TaskStatus.TODO.value,
            deadline=today + timedelta(hours=17, minutes=30),
            created_at=today,
        ),
        
        # Tomorrow's tasks
        Task(
            title="Design review session",
            description="Review new UI mockups",
            priority=TaskPriority.MEDIUM.value,
            status=TaskStatus.TODO.value,
            deadline=today + timedelta(days=1, hours=10),
            created_at=today,
        ),
        Task(
            title="Deploy to staging",
            description="Push latest changes to staging environment",
            priority=TaskPriority.HIGH.value,
            status=TaskStatus.TODO.value,
            deadline=today + timedelta(days=1, hours=14),
            created_at=today,
        ),
        Task(
            title="Team building activity",
            description="Virtual escape room",
            priority=TaskPriority.LOW.value,
            status=TaskStatus.TODO.value,
            deadline=today + timedelta(days=1, hours=16),
            created_at=today,
        ),
        
        # This week's tasks
        Task(
            title="Quarterly planning meeting",
            description="Plan Q1 2024 goals",
            priority=TaskPriority.URGENT.value,
            status=TaskStatus.TODO.value,
            deadline=today + timedelta(days=2, hours=10),
            created_at=today,
        ),
        Task(
            title="Database migration",
            description="Migrate to new schema",
            priority=TaskPriority.HIGH.value,
            status=TaskStatus.TODO.value,
            deadline=today + timedelta(days=3, hours=15),
            created_at=today,
        ),
        Task(
            title="Security audit",
            description="Review authentication flow",
            priority=TaskPriority.URGENT.value,
            status=TaskStatus.TODO.value,
            deadline=today + timedelta(days=4, hours=11),
            created_at=today,
        ),
        Task(
            title="Client presentation",
            description="Demo new features",
            priority=TaskPriority.HIGH.value,
            status=TaskStatus.TODO.value,
            deadline=today + timedelta(days=5, hours=14),
            created_at=today,
        ),
        
        # Next week's tasks
        Task(
            title="Sprint planning",
            description="Plan next 2-week sprint",
            priority=TaskPriority.MEDIUM.value,
            status=TaskStatus.TODO.value,
            deadline=today + timedelta(days=7, hours=9),
            created_at=today,
        ),
        Task(
            title="Performance optimization",
            description="Optimize database queries",
            priority=TaskPriority.MEDIUM.value,
            status=TaskStatus.TODO.value,
            deadline=today + timedelta(days=8, hours=13),
            created_at=today,
        ),
        Task(
            title="User testing session",
            description="Test new onboarding flow",
            priority=TaskPriority.LOW.value,
            status=TaskStatus.TODO.value,
            deadline=today + timedelta(days=10, hours=15),
            created_at=today,
        ),
        
        # Next month's tasks
        Task(
            title="Annual review preparation",
            description="Prepare performance reviews",
            priority=TaskPriority.MEDIUM.value,
            status=TaskStatus.TODO.value,
            deadline=today + timedelta(days=20, hours=10),
            created_at=today,
        ),
        Task(
            title="Conference talk preparation",
            description="Prepare slides for tech conference",
            priority=TaskPriority.LOW.value,
            status=TaskStatus.TODO.value,
            deadline=today + timedelta(days=25, hours=14),
            created_at=today,
        ),
        Task(
            title="Budget planning",
            description="Q1 budget allocation",
            priority=TaskPriority.HIGH.value,
            status=TaskStatus.TODO.value,
            deadline=today + timedelta(days=28, hours=11),
            created_at=today,
        ),
        
        # Past tasks (completed)
        Task(
            title="Setup CI/CD pipeline",
            description="Configure GitHub Actions",
            priority=TaskPriority.HIGH.value,
            status=TaskStatus.COMPLETED.value,
            deadline=today - timedelta(days=3, hours=15),
            completed_at=today - timedelta(days=3, hours=14),
            created_at=today - timedelta(days=5),
        ),
        Task(
            title="Implement authentication",
            description="JWT-based auth system",
            priority=TaskPriority.URGENT.value,
            status=TaskStatus.COMPLETED.value,
            deadline=today - timedelta(days=5, hours=12),
            completed_at=today - timedelta(days=5, hours=11, minutes=30),
            created_at=today - timedelta(days=7),
        ),
    ]
    
    db.add_all(mock_tasks)
    db.commit()
    
    count = len(mock_tasks)
    print(f"✅ Successfully seeded {count} mock tasks")
    
    db.close()


if __name__ == "__main__":
    seed_tasks()

