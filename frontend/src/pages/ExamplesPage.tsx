import RevealSection from '../components/common/RevealSection';
import HomeExamplesSection from '../components/home/HomeExamplesSection';

export default function ExamplesPage() {
  return (
    <div className="page examples-page">
      <RevealSection delayMs={0} variant="panel" className="home-scene home-scene-examples">
        <HomeExamplesSection standalone />
      </RevealSection>
    </div>
  );
}
