import { Link } from "react-router-dom";

export default function Rail({ actif }: { actif: "projets" | "templates" }) {
  return (
    <div className="rail">
      <div>
        <div className="marque">Fresque</div>
        <div>atelier local</div>
      </div>
      <nav>
        <Link to="/" className={actif === "projets" ? "actif" : undefined}>
          Documentaires
        </Link>
        <Link to="/templates" className={actif === "templates" ? "actif" : undefined}>
          Templates
        </Link>
      </nav>
    </div>
  );
}
