import Motion from '../components/Motion';
import {
  Comparison, Compete, Cta, Hero, NotJustALog, RankUp, Rival, TrainingIdentity,
} from '../components/Sections';

export default function Page() {
  return (
    <main>
      <Motion />
      <Hero />
      <NotJustALog />
      <TrainingIdentity />
      <RankUp />
      <Compete />
      <Rival />
      <Comparison />
      <Cta />
    </main>
  );
}
