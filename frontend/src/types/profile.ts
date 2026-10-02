export interface LearnerProfile {
  user_id: string;
  name: string | null;
  email: string | null;
  field_of_study: string | null;
  onboarding_complete: boolean;
  learning_goals: string[];
  completed_topics: string[];
  current_topics: string[];
  preferred_explanation_style: string | null;
  skill_level: string;
  previous_mistakes: string[];
  ongoing_projects: string[];
  interests: string[];
}

export interface OnboardingAnswers {
  name: string;
  field_of_study: string;
  topics_of_interest: string[];
  skill_level: string;
  preferred_explanation_style: string;
  goals: string[];
}
