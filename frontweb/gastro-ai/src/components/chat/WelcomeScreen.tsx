import { SUGGESTED_QUESTIONS } from '../../api/mockData';
import { MEDICAL_DISCLAIMER } from '../../utils/constants';
import { IconInfo, IconMessageSquare, IconStethoscope } from '../common/Icons';

interface WelcomeScreenProps {
  onPick: (question: string) => void;
}

export function WelcomeScreen({ onPick }: WelcomeScreenProps) {
  return (
    <div className="welcome-wrap">
      <div className="welcome-icon">
        <IconStethoscope size={26} />
      </div>
      <h1>How can I help you understand your digestive health?</h1>
      <p className="welcome-sub">
        Ask about symptoms, conditions, or treatments related to the stomach and digestive
        system. Every answer is grounded in retrieved medical sources.
      </p>

      <div className="suggestion-grid">
        {SUGGESTED_QUESTIONS.map((q) => (
          <button key={q} className="suggestion-card" onClick={() => onPick(q)}>
            <IconMessageSquare size={16} />
            <span>{q}</span>
          </button>
        ))}
      </div>

      <div className="disclaimer-strip">
        <IconInfo size={13} />
        <span>{MEDICAL_DISCLAIMER}</span>
      </div>
    </div>
  );
}
