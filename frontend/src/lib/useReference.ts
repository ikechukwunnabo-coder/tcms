import { useQuery } from "@tanstack/react-query";
import { getList } from "../api/client";
import type {
  CertificateType,
  Company,
  ContactType,
  CorporateAccount,
  Course,
  Instructor,
  Nationality,
  Position,
  State,
  Title,
  Venue,
} from "../api/types";

const params = { page_size: 200 };

export function useReference() {
  return useQuery({
    queryKey: ["reference"],
    staleTime: 5 * 60_000,
    queryFn: async () => {
      const [
        companies,
        nationalities,
        states,
        positions,
        titles,
        contactTypes,
        courses,
        certificateTypes,
        venues,
        instructors,
        accounts,
      ] = await Promise.all([
        getList<Company>("/companies/", { ...params, active: true }),
        getList<Nationality>("/nationalities/", params),
        getList<State>("/states/", params),
        getList<Position>("/positions/", params),
        getList<Title>("/titles/", params),
        getList<ContactType>("/contact-types/", params),
        getList<Course>("/courses/", params),
        getList<CertificateType>("/certificate-types/", params),
        getList<Venue>("/venues/", params),
        getList<Instructor>("/instructors/", params),
        getList<CorporateAccount>("/corporate-accounts/", params),
      ]);
      return {
        companies: companies.data,
        nationalities: nationalities.data,
        states: states.data,
        positions: positions.data,
        titles: titles.data,
        contactTypes: contactTypes.data,
        courses: courses.data,
        certificateTypes: certificateTypes.data,
        venues: venues.data,
        instructors: instructors.data,
        accounts: accounts.data,
      };
    },
  });
}
